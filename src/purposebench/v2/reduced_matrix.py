"""Reduced governed-action frontier matrix after compatibility exclusions."""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import (
    append_jsonl,
    read_jsonl,
    sha256_file,
    sha256_json,
)
from purposebench.v2.claude_compatibility import AUTHORIZATION_ID, _safe_provider_failure
from purposebench.v2.frontier_matrix import committed_budget_eur, load_frontier_matrix
from purposebench.v2.inference_pilot import _disclosure_findings
from purposebench.v2.phase_budget import (
    committed_category_eur,
    reserve_phase_budget,
    settle_phase_budget,
)
from purposebench.v2.pilots import write_new_v2_artifact
from purposebench.v2.position_diagnostic import (
    build_position_invocation,
    load_position_context,
)
from purposebench.v2.remote_pilot import _node_binary, invoke_openrouter_bridge

REDUCED_CATEGORY = "reduced_matrix"


def load_reduced_context(
    root: Path,
    config_path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    config, _ = load_position_context(root, config_path)
    reduced = config.get("eligibleReducedMatrix")
    if not isinstance(reduced, dict):
        raise TypeError("eligible reduced matrix configuration is missing")
    expected_models = [
        "openai/gpt-5.6-luna",
        "google/gemma-4-26b-a4b-it",
        "moonshotai/kimi-k3",
        "meta-llama/llama-4-maverick",
    ]
    if (
        reduced.get("modelIds") != expected_models
        or reduced.get("excludedModelIds")
        != {
            "anthropic/claude-opus-5": "FORMALLY_CLOSED_AT_GATE_1",
            "deepseek/deepseek-v4-pro": "FAILED_ELIGIBLE_POSITION_DIAGNOSTIC",
        }
        or int(reduced["repetitions"]) != 2
        or int(reduced["recordCount"]) != 40
        or float(reduced["maximumMatrixBudgetEur"])
        != float(config["budget"]["categories"][REDUCED_CATEGORY])
        or (root / reduced["modelMatrix"]).resolve()
        != (
            root / "docs/v2/model-manifests/openrouter-frontier-2026-08-04.json"
        ).resolve()
    ):
        raise ValueError("eligible reduced matrix controls are invalid")
    position_path = root / "results/v2/derived/openrouter-position-diagnostic.json"
    position = json.loads(position_path.read_text(encoding="utf-8"))
    position_material = dict(position)
    position_hash = position_material.pop("reportHash", None)
    if (
        position.get("status") != "COMPLETE_WITH_MODEL_FAILURE"
        or position_hash != sha256_json(position_material)
    ):
        raise ValueError("position diagnostic report is invalid")
    by_model = {model["modelId"]: model for model in position["models"]}
    if (
        by_model["openai/gpt-5.6-luna"]["eligibleForReducedGovernedMatrix"] is not True
        or by_model["deepseek/deepseek-v4-pro"]["eligibleForReducedGovernedMatrix"]
        is not False
    ):
        raise ValueError("position diagnostic eligibility changed")
    _, matrix_models = load_frontier_matrix(
        root,
        root / "configs/v2/openrouter-frontier-matrix.json",
    )
    selected = {
        str(model["modelId"]): model
        for model in matrix_models
        if model["modelId"] in expected_models
    }
    if set(selected) != set(expected_models):
        raise ValueError("eligible reduced matrix manifests are missing")
    config["positionDiagnosticReportHash"] = position_hash
    return config, selected


def reduced_plan(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    reduced = config["eligibleReducedMatrix"]
    return [
        {
            "stage": "smoke",
            "repetition": 0,
            "recordCount": int(reduced["smokeRecordCount"]),
            "invocationId": "smoke",
        },
        *[
            {
                "stage": "matrix",
                "repetition": repetition,
                "recordCount": int(reduced["recordCount"]),
                "invocationId": f"matrix-repetition-{repetition}",
            }
            for repetition in range(1, int(reduced["repetitions"]) + 1)
        ],
    ]


def build_reduced_invocation(
    *,
    root: Path,
    platform_root: Path,
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
    plan_item: Mapping[str, Any],
) -> dict[str, Any]:
    from purposebench.v2.inference_pilot import load_paired_records

    rows = load_paired_records(root / config["dataset"], pair_limit=20)[
        : int(plan_item["recordCount"])
    ]
    invocation = {
        "layout": "full_batch" if plan_item["stage"] == "matrix" else "one_record_smoke",
        "batch": 1,
        "invocationId": plan_item["invocationId"],
        "rows": rows,
    }
    material = build_position_invocation(
        root=root,
        platform_root=platform_root,
        config=config,
        manifest=manifest,
        invocation=invocation,
    )
    reduced = config["eligibleReducedMatrix"]
    contract = dict(material["contractMaterial"])
    contract.update(
        {
            "phase": "eligible_reduced_matrix",
            "matrixStage": plan_item["stage"],
            "repetition": plan_item["repetition"],
            "positionDiagnosticReportHash": config["positionDiagnosticReportHash"],
            "maximumAuthorizedCostEur": float(
                reduced["maximumReservationPerInvocationEur"]
            ),
        }
    )
    contract_hash = sha256_json(contract)
    payload = dict(material["payload"])
    payload.update(
        {
            "contractHash": contract_hash,
            "maximumAuthorizedCostEur": float(
                reduced["maximumReservationPerInvocationEur"]
            ),
            "outputTokenLimit": min(
                int(reduced["maximumOutputTokens"]),
                max(512, len(rows) * 72),
            ),
            "timeoutMs": int(reduced["timeoutMs"]),
        }
    )
    contract["outputTokenLimit"] = payload["outputTokenLimit"]
    contract["timeoutMs"] = payload["timeoutMs"]
    contract_hash = sha256_json(contract)
    payload["contractHash"] = contract_hash
    return {
        **material,
        "contractMaterial": contract,
        "contractHash": contract_hash,
        "payload": payload,
        "planItem": dict(plan_item),
    }


def probe_reduced_model(
    *,
    root: Path,
    platform_root: Path,
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    results = []
    for plan_item in reduced_plan(config):
        material = build_reduced_invocation(
            root=root,
            platform_root=platform_root,
            config=config,
            manifest=manifest,
            plan_item=plan_item,
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
            raise RuntimeError("eligible reduced-matrix fake-transport probe failed")
        probe = json.loads(completed.stdout)
        if probe.get("status") != "PASSED" or probe.get("externalProviderCalls") != 0:
            raise RuntimeError("eligible reduced-matrix fake evidence is invalid")
        results.append({"invocationId": plan_item["invocationId"], **probe})
    return {
        "status": "PASSED",
        "modelId": manifest["modelId"],
        "probedInvocations": len(results),
        "externalProviderCalls": 0,
        "results": results,
    }


def run_reduced_model_invocation(
    *,
    root: Path,
    platform_root: Path,
    config: Mapping[str, Any],
    manifest: Mapping[str, Any],
    invocation_id: str,
) -> Path:
    plan = reduced_plan(config)
    matches = [item for item in plan if item["invocationId"] == invocation_id]
    if len(matches) != 1:
        raise ValueError("reduced matrix invocation is unknown")
    plan_item = matches[0]
    slug = str(manifest["artifactSlug"])
    stem = f"openrouter-phase2-reduced-{slug}"
    final_path = root / f"results/v2/raw/inference/{stem}.jsonl"
    partial_path = final_path.with_suffix(".jsonl.partial")
    manifest_path = root / f"results/v2/manifests/{stem}.json"
    if final_path.exists():
        if not manifest_path.exists():
            raise ValueError("reduced matrix final artifact has no manifest")
        return manifest_path
    existing = read_jsonl(partial_path)
    if any(row.get("invocationId") == invocation_id for row in existing):
        raise RuntimeError("reduced matrix invocation already has immutable evidence")
    prerequisite_ids = {
        str(item["invocationId"])
        for item in plan
        if plan.index(item) < plan.index(plan_item)
    }
    passed_ids = {
        str(row["invocationId"]) for row in existing if row.get("status") == "passed"
    }
    if not prerequisite_ids.issubset(passed_ids):
        raise RuntimeError("reduced matrix invocation prerequisites have not passed")
    material = build_reduced_invocation(
        root=root,
        platform_root=platform_root,
        config=config,
        manifest=manifest,
        plan_item=plan_item,
    )
    reduced = config["eligibleReducedMatrix"]
    reservation_amount = float(reduced["maximumReservationPerInvocationEur"])
    phase = f"reduced_{slug}_{invocation_id}"
    reservation_id, _, _ = reserve_phase_budget(
        root / config["budget"]["ledger"],
        model_id=manifest["modelId"],
        phase=phase,
        category=REDUCED_CATEGORY,
        authorization_id=AUTHORIZATION_ID,
        authorized_cost_eur=reservation_amount,
        category_authorized_eur=float(reduced["maximumMatrixBudgetEur"]),
        absolute_authorized_eur=float(config["budget"]["absoluteAuthorizedEur"]),
    )
    started = datetime.now(UTC)
    tick = time.perf_counter()
    provider_evidence: dict[str, Any] | None = None
    provider_cost: Mapping[str, Any] | None = None
    error: Exception | None = None
    result: dict[str, Any] | None = None
    try:
        result = invoke_openrouter_bridge(
            benchmark_root=root,
            platform_root=platform_root,
            payload=material["payload"],
        )
        provider_evidence = result["evidence"]
        provider_cost = provider_evidence.get("providerReportedCost")
        raw_output = result["quarantinedOutput"]
        parsed = json.loads(raw_output)
        findings = _disclosure_findings(raw_output, material["rows"])
        governed = result["governedActionBatch"]
        native_release = result["nativeRelease"]
        cost = provider_evidence.get("cost", {}).get("amountEur")
        if (
            native_release.get("allowed") is not True
            or findings
            or governed.get("policyHash") != config["actionPolicyHash"]
            or governed.get("recordCount") != len(material["rows"])
            or governed.get("modelOutputHash") != sha256_json(parsed)
            or not isinstance(cost, (int, float))
            or not 0 <= cost <= reservation_amount
        ):
            raise ValueError("reduced matrix output failed release, mapping, or cost controls")
    except Exception as caught:  # noqa: BLE001 - every paid failure is retained safely
        error = caught

    if error is not None or result is None or provider_evidence is None:
        failure_error = error or RuntimeError("reduced matrix evidence is missing")
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
            category=REDUCED_CATEGORY,
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
                "schemaVersion": "purposebound-finance.reduced-matrix.v2",
                "recordType": "reduced_matrix_invocation",
                "evidenceId": str(uuid.uuid4()),
                "status": "failed",
                "processingClassification": "REMOTE_PROVIDER_PROCESSING",
                "modelId": manifest["modelId"],
                "modelManifestHash": manifest["manifestHash"],
                "invocationId": invocation_id,
                "matrixStage": plan_item["stage"],
                "repetition": plan_item["repetition"],
                "startedAt": started.isoformat(),
                "finishedAt": datetime.now(UTC).isoformat(),
                "durationSeconds": round(time.perf_counter() - tick, 3),
                "contractMaterial": material["contractMaterial"],
                "contractHash": material["contractHash"],
                "providerCalls": 1,
                "retryCount": 0,
                "providerDiagnostic": _safe_provider_failure(failure_error, safe_manifest),
                "budget": {
                    "reservationId": reservation_id,
                    "conservativeDebitEur": debit,
                    "providerReportedCost": provider_cost,
                    "globalCommittedEur": global_committed,
                    "categoryCommittedEur": category_committed,
                },
            },
        )
        raise RuntimeError(f"reduced matrix failed closed: {invocation_id}") from None

    parsed = json.loads(result["quarantinedOutput"])
    cost = float(provider_evidence["cost"]["amountEur"])
    global_committed, category_committed = settle_phase_budget(
        root / config["budget"]["ledger"],
        reservation_id=reservation_id,
        model_id=manifest["modelId"],
        phase=phase,
        category=REDUCED_CATEGORY,
        authorization_id=AUTHORIZATION_ID,
        budget_debit_eur=cost,
        outcome="passed",
        provider_reported_cost=provider_cost,
    )
    append_jsonl(
        partial_path,
        {
            "schemaVersion": "purposebound-finance.reduced-matrix.v2",
            "recordType": "reduced_matrix_invocation",
            "evidenceId": str(uuid.uuid4()),
            "status": "passed",
            "processingClassification": "REMOTE_PROVIDER_PROCESSING",
            "modelId": manifest["modelId"],
            "modelManifestHash": manifest["manifestHash"],
            "invocationId": invocation_id,
            "matrixStage": plan_item["stage"],
            "repetition": plan_item["repetition"],
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
            "releasedModelOutput": parsed,
            "releasedModelOutputHash": sha256_json(parsed),
            "governedActionBatch": result["governedActionBatch"],
            "nativeReleaseEvidence": result["nativeRelease"],
            "releaseAllowed": True,
            "disclosureFindings": _disclosure_findings(
                result["quarantinedOutput"],
                material["rows"],
            ),
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
        "schemaVersion": "purposebound-finance.reduced-matrix-manifest.v2",
        "status": "PASSED",
        "scope": "ELIGIBLE_MODELS_AFTER_COMPATIBILITY_EXCLUSIONS",
        "modelId": manifest["modelId"],
        "modelManifestHash": manifest["manifestHash"],
        "actionPolicyHash": config["actionPolicyHash"],
        "positionDiagnosticReportHash": config["positionDiagnosticReportHash"],
        "rawArtifact": final_path.relative_to(root).as_posix(),
        "rawArtifactSha256": sha256_file(final_path),
        "smokeCalls": 1,
        "matrixRepetitions": 2,
        "matrixRecordCountPerRepetition": 40,
        "providerCalls": len(accumulated),
        "retryCount": 0,
        "budgetLedgerPrefixRecordCount": len(ledger),
        "budgetLedgerPrefixHash": sha256_json(ledger),
        "budgetCategory": REDUCED_CATEGORY,
        "categoryCommittedEur": committed_category_eur(ledger, REDUCED_CATEGORY),
        "globalCommittedEur": committed_budget_eur(ledger),
    }
    return write_new_v2_artifact(root, manifest_path.relative_to(root), result_manifest)
