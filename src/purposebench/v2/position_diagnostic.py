"""Eligible-model position diagnostics after formal Claude closure."""

from __future__ import annotations

import json
import os
import random
import subprocess
import time
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import (
    append_jsonl,
    git_commit,
    read_jsonl,
    sha256_file,
    sha256_json,
    sha256_text,
)
from purposebench.v2.claude_compatibility import (
    AUTHORIZATION_ID,
    _safe_provider_failure,
    assessment_prompts,
    assessment_schema,
    load_phase_configuration,
)
from purposebench.v2.frontier_matrix import committed_budget_eur, load_frontier_matrix
from purposebench.v2.inference_pilot import (
    _disclosure_findings,
    load_paired_records,
    native_release_policy,
)
from purposebench.v2.phase_budget import (
    committed_category_eur,
    reserve_phase_budget,
    settle_phase_budget,
)
from purposebench.v2.pilots import write_new_v2_artifact
from purposebench.v2.remote_pilot import (
    _node_binary,
    invoke_openrouter_bridge,
    prepare_remote_batch,
)

POSITION_CATEGORY = "position_diagnostic"


def position_layouts(
    rows: Sequence[Mapping[str, Any]],
    *,
    pair_count: int,
    seed: int,
) -> list[dict[str, Any]]:
    if len(rows) != 40 or pair_count != 4:
        raise ValueError("position diagnostic requires the frozen 40-record dataset and four pairs")
    base = list(rows[: pair_count * 2])
    pair_order = list(dict.fromkeys(str(row["pair_id"]) for row in base))
    by_pair = {
        pair_id: [row for row in base if str(row["pair_id"]) == pair_id]
        for pair_id in pair_order
    }
    if any({str(row["variant"]) for row in pair} != {"A", "B"} for pair in by_pair.values()):
        raise ValueError("position diagnostic input pairs are incomplete")
    shuffled = list(base)
    random.Random(seed).shuffle(shuffled)
    adjacent = [
        row
        for pair_id in pair_order
        for row in sorted(by_pair[pair_id], key=lambda item: str(item["variant"]))
    ]
    separated = [row for variant in ("A", "B") for row in base if row["variant"] == variant]
    swapped = [
        row
        for pair_id in pair_order
        for row in sorted(
            by_pair[pair_id],
            key=lambda item: 0 if item["variant"] == "B" else 1,
        )
    ]
    layouts: list[tuple[str, list[list[Mapping[str, Any]]]]] = [
        ("original_order", [base]),
        ("reversed_order", [list(reversed(base))]),
        ("deterministic_shuffle", [shuffled]),
        ("adjacent_pairs", [adjacent]),
        ("separated_pairs", [separated]),
        ("swapped_ab_positions", [swapped]),
        ("singleton_calls", [[base[0]], [base[1]]]),
        ("small_batches", [base[:4], base[4:]]),
        ("full_batch", [list(rows)]),
    ]
    return [
        {
            "layout": layout,
            "batch": batch_index,
            "invocationId": f"{layout}-batch{batch_index}",
            "rows": batch,
        }
        for layout, batches in layouts
        for batch_index, batch in enumerate(batches, start=1)
    ]


def load_position_context(
    root: Path,
    config_path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    config = load_phase_configuration(root, config_path)
    diagnostic = config.get("eligiblePositionDiagnostic")
    if not isinstance(diagnostic, dict):
        raise TypeError("eligible position diagnostic configuration is missing")
    category_budget = float(config["budget"]["categories"][POSITION_CATEGORY])
    if (
        diagnostic.get("claudeGate3") is not False
        or float(diagnostic["maximumDiagnosticBudgetEur"]) != category_budget
        or not 0 < float(diagnostic["maximumReservationPerInvocationEur"]) <= category_budget
        or diagnostic.get("modelIds")
        != ["openai/gpt-5.6-luna", "deepseek/deepseek-v4-pro"]
    ):
        raise ValueError("eligible position diagnostic controls are invalid")
    closure_path = root / "results/v2/derived/openrouter-claude-closure.json"
    closure = json.loads(closure_path.read_text(encoding="utf-8"))
    closure_material = dict(closure)
    closure_hash = closure_material.pop("closureHash", None)
    if (
        closure.get("status") != "FORMALLY_CLOSED"
        or closure_hash != sha256_json(closure_material)
        or closure.get("remainingExperimentPolicy", {}).get("claudeEligible") is not False
    ):
        raise ValueError("Claude closure is not valid for remaining-model diagnostics")
    matrix_path = root / diagnostic["modelMatrix"]
    _, models = load_frontier_matrix(
        root,
        root / "configs/v2/openrouter-frontier-matrix.json",
    )
    if matrix_path.resolve() != (
        root / "docs/v2/model-manifests/openrouter-frontier-2026-08-04.json"
    ).resolve():
        raise ValueError("position diagnostic model matrix was substituted")
    selected = {
        str(model["modelId"]): model
        for model in models
        if model["modelId"] in diagnostic["modelIds"]
    }
    if set(selected) != set(diagnostic["modelIds"]):
        raise ValueError("position diagnostic models are missing")
    config["claudeClosureHash"] = closure_hash
    return config, selected


def _manifest_strategy(manifest: Mapping[str, Any]) -> dict[str, Any]:
    supported = set(map(str, manifest["supportedParameters"]))
    token_parameter = "max_tokens" if "max_tokens" in supported else "max_completion_tokens"
    return {
        "tokenParameter": token_parameter,
        "reasoningSetting": manifest.get("reasoningSetting", "DISABLED"),
        "reasoningDisableStrategy": manifest.get(
            "reasoningDisableStrategy",
            "ENABLED_FALSE",
        ),
    }


def build_position_invocation(
    *,
    root: Path,
    platform_root: Path,
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
    invocation: Mapping[str, Any],
) -> dict[str, Any]:
    rows = invocation["rows"]
    dataset_path = root / config["dataset"]
    records, selected_fields, denied_fields, pseudonymized_fields = prepare_remote_batch(
        rows,
        dataset_sha256=sha256_file(dataset_path),
    )
    schema = assessment_schema(len(rows), config["actionPolicyValue"])
    prompts = assessment_prompts()
    diagnostic = config["eligiblePositionDiagnostic"]
    supported = set(map(str, manifest["supportedParameters"]))
    seed = int(diagnostic["seed"]) if "seed" in supported else None
    output_limit = min(
        int(diagnostic["maximumOutputTokens"]),
        max(512, len(rows) * 72),
    )
    route = str(manifest["providerRouting"]["only"][0])
    strategy = _manifest_strategy(manifest)
    case_ids = [str(row["case_id"]) for row in rows]
    contract_material = {
        "protocolId": config["protocolId"],
        "phase": "eligible_position_diagnostic",
        "layout": invocation["layout"],
        "layoutBatch": invocation["batch"],
        "invocationId": invocation["invocationId"],
        "gateway": "OPENROUTER",
        "modelId": manifest["modelId"],
        "canonicalCatalogSlug": manifest["canonicalSlug"],
        "upstreamRoute": route,
        "modelManifestHash": manifest["manifestHash"],
        "catalogMetadataHash": manifest["metadataResponseSha256"],
        "routeMetadataHash": manifest["routingEndpointSnapshotSha256"],
        "claudeClosureHash": config["claudeClosureHash"],
        "actionPolicyHash": config["actionPolicyHash"],
        "responseSchemaHash": sha256_json(schema),
        "promptHashes": {key: sha256_text(value) for key, value in prompts.items()},
        "selectedFields": list(selected_fields),
        "deniedFields": list(denied_fields),
        "pseudonymizedFields": list(pseudonymized_fields),
        "orderedCaseIdsHash": sha256_json(case_ids),
        "transmittedRecordsHash": sha256_json(records),
        "recordCount": len(rows),
        "outputTokenLimit": output_limit,
        "timeoutMs": int(diagnostic["timeoutMs"]),
        "seed": seed,
        **strategy,
        "routing": {
            "fallbackAllowed": False,
            "zeroDataRetentionRequired": True,
            "providerDataCollectionAllowed": False,
            "requireParameters": True,
        },
        "maximumCalls": 1,
        "retryCount": 0,
        "platformCommit": git_commit(platform_root),
        "openRouterBridgeSha256": sha256_file(root / "scripts/governed_openrouter_bridge.cjs"),
    }
    contract_hash = sha256_json(contract_material)
    return {
        "contractMaterial": contract_material,
        "contractHash": contract_hash,
        "orderedCaseIds": case_ids,
        "selectedFields": selected_fields,
        "deniedFields": denied_fields,
        "pseudonymizedFields": pseudonymized_fields,
        "rows": rows,
        "payload": {
            "contractHash": contract_hash,
            "modelManifest": manifest,
            "workloadImageDigest": "sha256:" + "0" * 64,
            "seed": seed,
            "outputTokenLimit": output_limit,
            "timeoutMs": int(diagnostic["timeoutMs"]),
            "selectedFields": list(selected_fields),
            "records": records,
            "prompts": prompts,
            "responseSchema": schema,
            "nativeReleasePolicy": native_release_policy(schema, rows),
            "actionPolicy": config["actionPolicyValue"],
            "actionPolicyHash": config["actionPolicyHash"],
            "expectedRecordCount": len(rows),
            "maximumAuthorizedCostEur": float(
                diagnostic["maximumReservationPerInvocationEur"]
            ),
        },
    }


def probe_position_model(
    *,
    root: Path,
    platform_root: Path,
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
    layout: str | None = None,
) -> dict[str, Any]:
    rows = load_paired_records(root / config["dataset"], pair_limit=20)
    plan = position_layouts(
        rows,
        pair_count=int(config["eligiblePositionDiagnostic"]["pairCount"]),
        seed=int(config["eligiblePositionDiagnostic"]["seed"]),
    )
    selected = [item for item in plan if layout is None or item["layout"] == layout]
    if not selected:
        raise ValueError("position diagnostic layout is unknown")
    results = []
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    for invocation in selected:
        material = build_position_invocation(
            root=root,
            platform_root=platform_root,
            config=config,
            manifest=manifest,
            invocation=invocation,
        )
        completed = subprocess.run(
            [_node_binary(), str(root / "scripts/probe_openrouter_bridge.cjs")],
            input=json.dumps(material["payload"], sort_keys=True, separators=(",", ":")),
            capture_output=True,
            text=True,
            env=environment,
            timeout=30,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("eligible position fake-transport probe failed")
        result = json.loads(completed.stdout)
        if result.get("status") != "PASSED" or result.get("externalProviderCalls") != 0:
            raise RuntimeError("eligible position fake-transport probe evidence is invalid")
        results.append({"invocationId": invocation["invocationId"], **result})
    return {
        "status": "PASSED",
        "modelId": manifest["modelId"],
        "probedInvocations": len(results),
        "externalProviderCalls": 0,
        "results": results,
    }


def run_position_model(
    *,
    root: Path,
    platform_root: Path,
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
    layout: str | None = None,
) -> Path:
    slug = str(manifest["artifactSlug"])
    stem = f"openrouter-phase2-position-{slug}"
    final_path = root / f"results/v2/raw/inference/{stem}.jsonl"
    partial_path = final_path.with_suffix(".jsonl.partial")
    manifest_path = root / f"results/v2/manifests/{stem}.json"
    if final_path.exists():
        if not manifest_path.exists():
            raise ValueError("position diagnostic final artifact has no manifest")
        return manifest_path
    rows = load_paired_records(root / config["dataset"], pair_limit=20)
    plan = position_layouts(
        rows,
        pair_count=int(config["eligiblePositionDiagnostic"]["pairCount"]),
        seed=int(config["eligiblePositionDiagnostic"]["seed"]),
    )
    selected = [item for item in plan if layout is None or item["layout"] == layout]
    if not selected:
        raise ValueError("position diagnostic layout is unknown")
    existing = read_jsonl(partial_path)
    completed_ids = {str(row["invocationId"]) for row in existing}
    for invocation in selected:
        if invocation["invocationId"] in completed_ids:
            continue
        material = build_position_invocation(
            root=root,
            platform_root=platform_root,
            config=config,
            manifest=manifest,
            invocation=invocation,
        )
        diagnostic_config = config["eligiblePositionDiagnostic"]
        reservation_amount = float(
            diagnostic_config["maximumReservationPerInvocationEur"]
        )
        phase = f"position_{slug}_{invocation['invocationId']}"
        reservation_id, _, _ = reserve_phase_budget(
            root / config["budget"]["ledger"],
            model_id=manifest["modelId"],
            phase=phase,
            category=POSITION_CATEGORY,
            authorization_id=AUTHORIZATION_ID,
            authorized_cost_eur=reservation_amount,
            category_authorized_eur=float(diagnostic_config["maximumDiagnosticBudgetEur"]),
            absolute_authorized_eur=float(config["budget"]["absoluteAuthorizedEur"]),
        )
        started = datetime.now(UTC)
        tick = time.perf_counter()
        provider_evidence: dict[str, Any] | None = None
        provider_cost: Mapping[str, Any] | None = None
        error: Exception | None = None
        invocation_result: dict[str, Any] | None = None
        try:
            invocation_result = invoke_openrouter_bridge(
                benchmark_root=root,
                platform_root=platform_root,
                payload=material["payload"],
            )
            provider_evidence = invocation_result["evidence"]
            provider_cost = provider_evidence.get("providerReportedCost")
            native_release = invocation_result["nativeRelease"]
            governed = invocation_result["governedActionBatch"]
            raw_output = invocation_result["quarantinedOutput"]
            parsed_output = json.loads(raw_output)
            findings = _disclosure_findings(raw_output, material["rows"])
            cost = provider_evidence.get("cost", {}).get("amountEur")
            if (
                native_release.get("allowed") is not True
                or findings
                or governed.get("policyHash") != config["actionPolicyHash"]
                or governed.get("recordCount") != len(material["rows"])
                or governed.get("modelOutputHash") != sha256_json(parsed_output)
                or not isinstance(cost, (int, float))
                or not 0 <= cost <= reservation_amount
            ):
                raise ValueError("position output failed release, mapping, or cost controls")
        except Exception as caught:  # noqa: BLE001 - every paid failure is persisted safely
            error = caught

        if error is not None or invocation_result is None or provider_evidence is None:
            failure_error = error or RuntimeError("position invocation evidence is missing")
            debit = reservation_amount
            if provider_evidence is not None:
                observed = provider_evidence.get("cost", {}).get("amountEur")
                if isinstance(observed, (int, float)) and 0 <= observed <= reservation_amount:
                    debit = float(observed)
            global_committed, category_committed = settle_phase_budget(
                root / config["budget"]["ledger"],
                reservation_id=reservation_id,
                model_id=manifest["modelId"],
                phase=phase,
                category=POSITION_CATEGORY,
                authorization_id=AUTHORIZATION_ID,
                budget_debit_eur=debit,
                outcome=(
                    "failed_conservative_debit"
                    if provider_evidence is None
                    else "failed_known_debit"
                ),
                provider_reported_cost=provider_cost,
            )
            safe_manifest = {"upstreamRoute": manifest["providerRouting"]["only"][0]}
            append_jsonl(
                partial_path,
                {
                    "schemaVersion": "purposebound-finance.position-diagnostic.v2",
                    "recordType": "position_diagnostic_invocation",
                    "evidenceId": str(uuid.uuid4()),
                    "status": "failed",
                    "processingClassification": "REMOTE_PROVIDER_PROCESSING",
                    "modelId": manifest["modelId"],
                    "modelManifestHash": manifest["manifestHash"],
                    "invocationId": invocation["invocationId"],
                    "layout": invocation["layout"],
                    "layoutBatch": invocation["batch"],
                    "startedAt": started.isoformat(),
                    "finishedAt": datetime.now(UTC).isoformat(),
                    "durationSeconds": round(time.perf_counter() - tick, 3),
                    "contractMaterial": material["contractMaterial"],
                    "contractHash": material["contractHash"],
                    "providerCalls": 1,
                    "retryCount": 0,
                    "providerDiagnostic": _safe_provider_failure(
                        failure_error,
                        safe_manifest,
                    ),
                    "budget": {
                        "reservationId": reservation_id,
                        "conservativeDebitEur": debit,
                        "providerReportedCost": provider_cost,
                        "globalCommittedEur": global_committed,
                        "categoryCommittedEur": category_committed,
                    },
                },
            )
            raise RuntimeError(
                f"eligible position invocation failed closed: {invocation['invocationId']}"
            ) from None

        raw_output = invocation_result["quarantinedOutput"]
        parsed_output = json.loads(raw_output)
        governed = invocation_result["governedActionBatch"]
        native_release = invocation_result["nativeRelease"]
        cost = float(provider_evidence["cost"]["amountEur"])
        global_committed, category_committed = settle_phase_budget(
            root / config["budget"]["ledger"],
            reservation_id=reservation_id,
            model_id=manifest["modelId"],
            phase=phase,
            category=POSITION_CATEGORY,
            authorization_id=AUTHORIZATION_ID,
            budget_debit_eur=cost,
            outcome="passed",
            provider_reported_cost=provider_cost,
        )
        append_jsonl(
            partial_path,
            {
                "schemaVersion": "purposebound-finance.position-diagnostic.v2",
                "recordType": "position_diagnostic_invocation",
                "evidenceId": str(uuid.uuid4()),
                "status": "passed",
                "processingClassification": "REMOTE_PROVIDER_PROCESSING",
                "modelId": manifest["modelId"],
                "modelManifestHash": manifest["manifestHash"],
                "invocationId": invocation["invocationId"],
                "layout": invocation["layout"],
                "layoutBatch": invocation["batch"],
                "startedAt": started.isoformat(),
                "finishedAt": datetime.now(UTC).isoformat(),
                "durationSeconds": round(time.perf_counter() - tick, 3),
                "contractMaterial": material["contractMaterial"],
                "contractHash": material["contractHash"],
                "orderedCaseIds": material["orderedCaseIds"],
                "transmittedFields": list(material["selectedFields"]),
                "prohibitedSyntheticFields": list(material["deniedFields"]),
                "prohibitedSyntheticFieldsTransmitted": False,
                "identifiersPseudonymized": bool(material["pseudonymizedFields"]),
                "releasedModelOutput": parsed_output,
                "releasedModelOutputHash": sha256_json(parsed_output),
                "governedActionBatch": governed,
                "nativeReleaseEvidence": native_release,
                "releaseAllowed": True,
                "disclosureFindings": [],
                "modelEvidence": provider_evidence,
                "providerCalls": 1,
                "retryCount": 0,
                "budget": {
                    "reservationId": reservation_id,
                    "conservativeDebitEur": cost,
                    "providerReportedCost": provider_cost,
                    "globalCommittedEur": global_committed,
                    "categoryCommittedEur": category_committed,
                },
            },
        )
        completed_ids.add(str(invocation["invocationId"]))

    accumulated = read_jsonl(partial_path)
    plan_ids = {str(item["invocationId"]) for item in plan}
    passed_ids = {
        str(row["invocationId"]) for row in accumulated if row.get("status") == "passed"
    }
    if passed_ids != plan_ids:
        return partial_path
    os.replace(partial_path, final_path)
    ledger = read_jsonl(root / config["budget"]["ledger"])
    result_manifest = {
        "schemaVersion": "purposebound-finance.position-diagnostic-manifest.v2",
        "status": "PASSED",
        "scope": "ELIGIBLE_MODELS_AFTER_CLAUDE_CLOSURE",
        "claudeGate3": False,
        "modelId": manifest["modelId"],
        "modelManifestHash": manifest["manifestHash"],
        "actionPolicyHash": config["actionPolicyHash"],
        "rawArtifact": final_path.relative_to(root).as_posix(),
        "rawArtifactSha256": sha256_file(final_path),
        "invocationCount": len(accumulated),
        "providerCalls": len(accumulated),
        "retryCount": 0,
        "layouts": sorted({str(row["layout"]) for row in accumulated}),
        "budgetLedgerPrefixRecordCount": len(ledger),
        "budgetLedgerPrefixHash": sha256_json(ledger),
        "budgetCategory": POSITION_CATEGORY,
        "categoryCommittedEur": committed_category_eur(ledger, POSITION_CATEGORY),
        "globalCommittedEur": committed_budget_eur(ledger),
    }
    return write_new_v2_artifact(root, manifest_path.relative_to(root), result_manifest)
