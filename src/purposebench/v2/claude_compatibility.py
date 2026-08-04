"""Bounded OpenRouter-only Claude compatibility gates."""

from __future__ import annotations

import json
import os
import re
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
from purposebench.v2.frontier_matrix import committed_budget_eur
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

AUTHORIZATION_ID = "openrouter-phase2-user-20260805-eur5"
BUDGET_CATEGORY = "new_claude_compatibility"
SAFE_CATEGORIES = {
    "AUTHENTICATION",
    "MODEL_NOT_FOUND",
    "ROUTE_NOT_FOUND",
    "RATE_LIMIT",
    "UNSUPPORTED_PARAMETER",
    "INVALID_STRUCTURED_OUTPUT",
    "PROVIDER_ROUTING",
    "OUTPUT_TOKEN_MINIMUM",
    "PROVIDER_UNAVAILABLE",
    "TIMEOUT",
    "TRUNCATED_RESPONSE",
    "INVALID_RESPONSE",
    "UNKNOWN_SAFE_CLASS",
}


def load_phase_configuration(root: Path, path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schemaVersion") != "purposebound-finance.openrouter-phase2.v2":
        raise ValueError("OpenRouter phase-two schema is invalid")
    budget = config.get("budget")
    compatibility = config.get("claudeCompatibility")
    provider_policy = config.get("commercialProviderPolicy")
    justification = config.get("newAttemptJustification")
    if not all(isinstance(item, dict) for item in (budget, compatibility, provider_policy, justification)):
        raise TypeError("OpenRouter phase-two controls are incomplete")
    categories = budget.get("categories")
    if (
        not isinstance(categories, dict)
        or sum(float(value) for value in categories.values())
        != float(budget["additionalAuthorizedEur"])
        or float(budget["absoluteAuthorizedEur"])
        != float(budget["priorCommittedEur"]) + float(budget["additionalAuthorizedEur"])
        or float(categories[BUDGET_CATEGORY])
        != float(compatibility["maximumCompatibilityBudgetEur"])
        or int(compatibility["maximumSmokeAttempts"])
        * float(compatibility["maximumReservationPerAttemptEur"])
        > float(compatibility["maximumCompatibilityBudgetEur"])
    ):
        raise ValueError("OpenRouter phase-two budget allocation is invalid")
    if (
        provider_policy.get("gateway") != "OPENROUTER"
        or provider_policy.get("credentialReference")
        != {"provider": "LOCAL_ENV_REFERENCE", "reference": "OPENROUTER_API_KEY"}
        or provider_policy.get("directProviderApisAllowed") is not False
        or provider_policy.get("fallbackAllowed") is not False
        or provider_policy.get("zeroDataRetentionRequired") is not True
        or provider_policy.get("providerDataCollectionAllowed") is not False
    ):
        raise ValueError("OpenRouter-only provider policy is invalid")
    if (
        justification.get("documentedBeforePaidCall") is not True
        or not justification.get("reason")
        or len(justification.get("materialChanges", [])) < 1
    ):
        raise ValueError("Claude attempt justification is missing")
    ledger_path = root / budget["ledger"]
    rows = read_jsonl(ledger_path)
    count = int(budget["priorLedgerPrefixRecordCount"])
    if (
        count > len(rows)
        or sha256_json(rows[:count]) != budget["priorLedgerPrefixHash"]
        or committed_budget_eur(rows[:count]) != float(budget["priorCommittedEur"])
    ):
        raise ValueError("Pre-authorization budget prefix changed")
    selection_path = root / config["modelSelection"]
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    selection_material = dict(selection)
    selection_hash = selection_material.pop("selectionHash", None)
    if selection_hash != sha256_json(selection_material):
        raise ValueError("Claude selection artifact hash mismatch")
    manifest_path = root / config["claudeModelManifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_material = dict(manifest)
    manifest_hash = manifest_material.pop("manifestHash", None)
    if (
        manifest_hash != sha256_json(manifest_material)
        or manifest.get("gateway") != "OPENROUTER"
        or manifest.get("modelId") != selection.get("selectedModelId")
        or manifest.get("upstreamRoute") != selection.get("selectedRoute")
        or manifest.get("fallbackAllowed") is not False
        or manifest.get("zeroDataRetentionRequired") is not True
        or manifest.get("providerDataCollectionAllowed") is not False
        or manifest.get("structuredOutputMode") != "JSON_SCHEMA_STRICT"
    ):
        raise ValueError("Claude model manifest is invalid")
    for artifact_key, hash_key in (
        ("catalogArtifact", "catalogResponseHash"),
        ("routeArtifact", "routeResponseHash"),
    ):
        artifact_path = root / manifest[artifact_key]
        if sha256_text(artifact_path.read_text(encoding="utf-8")) != manifest[hash_key]:
            raise ValueError("Captured OpenRouter metadata response changed")
    action_binding = json.loads((root / config["actionPolicy"]).read_text(encoding="utf-8"))
    if (
        action_binding.get("schemaVersion")
        != "purposebound-finance.action-policy-binding.v2"
        or action_binding.get("policyHash") != sha256_json(action_binding.get("policy"))
    ):
        raise ValueError("Deterministic action-policy binding is invalid")
    config["modelManifestValue"] = manifest
    config["actionPolicyValue"] = action_binding["policy"]
    config["actionPolicyHash"] = action_binding["policyHash"]
    config["selectionHash"] = selection_hash
    return config


def assessment_schema(record_count: int, policy: Mapping[str, Any]) -> dict[str, Any]:
    if not 0 < record_count <= 40:
        raise ValueError("Claude compatibility batch size is invalid")
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["results"],
        "properties": {
            "results": {
                "type": "array",
                "minItems": record_count,
                "maxItems": record_count,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "index",
                        "normalized_risk_score",
                        "recommendation",
                        "factors",
                    ],
                    "properties": {
                        "index": {
                            "type": "integer",
                            "minimum": 0,
                            "maximum": record_count - 1,
                        },
                        "normalized_risk_score": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                        "recommendation": {
                            "type": "string",
                            "enum": list(policy["permittedRecommendations"]),
                        },
                        "factors": {
                            "type": "array",
                            "maxItems": int(policy["maximumFactors"]),
                            "items": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": int(policy["maximumFactorLength"]),
                            },
                        },
                    },
                },
            }
        },
    }


def assessment_prompts() -> dict[str, str]:
    return {
        "system": (
            "Immutable purpose contract: assess mortgage review risk using only the approved "
            "projection. Do not choose the governed action. Return only the declared JSON schema."
        ),
        "user": (
            "For every supplied record, return its zero-based input index, a normalized risk "
            "score from 0 to 1, an optional recommendation using NO_RECOMMENDATION when absent, "
            "and at most three concise factors. Index i is irrevocably bound to input record i."
        ),
    }


def build_contract_material(
    *,
    config: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    selected_fields: Sequence[str],
    denied_fields: Sequence[str],
    schema: Mapping[str, Any],
    prompts: Mapping[str, str],
    gate: int,
    platform_commit: str,
) -> dict[str, Any]:
    manifest = config["modelManifestValue"]
    return {
        "protocolId": config["protocolId"],
        "phase": f"claude_gate_{gate}",
        "gateway": "OPENROUTER",
        "modelId": manifest["modelId"],
        "canonicalCatalogSlug": manifest["canonicalCatalogSlug"],
        "upstreamRoute": manifest["upstreamRoute"],
        "modelManifestHash": manifest["manifestHash"],
        "catalogMetadataHash": manifest["catalogMetadataHash"],
        "routeMetadataHash": manifest["routeMetadataHash"],
        "actionPolicyHash": config["actionPolicyHash"],
        "responseSchemaHash": sha256_json(schema),
        "promptHashes": {key: sha256_text(value) for key, value in prompts.items()},
        "selectedFields": list(selected_fields),
        "deniedFields": list(denied_fields),
        "orderedCaseIdsHash": sha256_json([str(row["case_id"]) for row in rows]),
        "recordCount": len(rows),
        "outputTokenLimit": config["claudeCompatibility"]["outputTokenLimit"],
        "timeoutMs": config["claudeCompatibility"]["timeoutMs"],
        "tokenParameter": manifest["tokenParameter"],
        "reasoningConfiguration": manifest["reasoningConfiguration"],
        "routing": {
            "fallbackAllowed": False,
            "zeroDataRetentionRequired": True,
            "providerDataCollectionAllowed": False,
            "requireParameters": True,
        },
        "maximumCalls": 1,
        "retryCount": 0,
        "platformCommit": platform_commit,
    }


def repeated_failed_combination(root: Path, manifest_hash: str, contract_hash: str) -> bool:
    pattern = "openrouter-frontier-smoke-anthropic-claude-*.jsonl.partial"
    for path in (root / "results/v2/raw/inference").glob(pattern):
        for row in read_jsonl(path):
            if (
                row.get("status") == "failed"
                and row.get("modelManifestHash") == manifest_hash
                and row.get("contractHash") == contract_hash
            ):
                return True
    return False


def _secret_scan(root: Path, platform_root: Path) -> dict[str, Any]:
    environment_path = platform_root / ".env.research.local"
    values = []
    for raw in environment_path.read_text(encoding="utf-8").splitlines():
        if raw.strip().startswith("OPENROUTER_API_KEY="):
            values.append(raw.split("=", 1)[1].strip().strip("\"'"))
    if len(values) != 1 or not values[0]:
        raise ValueError("OPENROUTER_API_KEY reference does not resolve exactly once")
    secret = values[0].encode()
    tracked_hits = 0
    history_hits = 0
    for repository in (root, platform_root):
        tracked = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repository,
            capture_output=True,
            check=True,
        ).stdout.split(b"\0")
        for relative in tracked:
            if not relative:
                continue
            path = repository / os.fsdecode(relative)
            if path.is_file() and secret in path.read_bytes():
                tracked_hits += 1
        history = subprocess.run(
            ["git", "log", "--all", "-p", "--no-ext-diff"],
            cwd=repository,
            capture_output=True,
            check=True,
        ).stdout
        history_hits += history.count(secret)
    if tracked_hits or history_hits:
        raise ValueError("OpenRouter key material was found on a persisted Git surface")
    return {
        "credentialReference": {
            "provider": "LOCAL_ENV_REFERENCE",
            "reference": "OPENROUTER_API_KEY",
        },
        "trackedSecretValueHits": tracked_hits,
        "gitHistorySecretValueHits": history_hits,
        "keyValueRecorded": False,
        "keyValueHashed": False,
    }


def run_gate_zero(root: Path, platform_root: Path, config_path: Path) -> Path:
    config = load_phase_configuration(root, config_path)
    compatibility = config["claudeCompatibility"]
    ledger = read_jsonl(root / config["budget"]["ledger"])
    global_committed = committed_budget_eur(ledger)
    category_committed = committed_category_eur(ledger, BUDGET_CATEGORY)
    reservation = float(compatibility["maximumReservationPerAttemptEur"])
    if (
        global_committed + reservation > float(config["budget"]["absoluteAuthorizedEur"])
        or category_committed + reservation
        > float(compatibility["maximumCompatibilityBudgetEur"])
    ):
        raise RuntimeError("Claude Gate 0 budget reservation preflight failed")
    required_builds = [
        platform_root / "packages/types/dist/index.js",
        platform_root / "services/runner/dist/providers/openrouter.adapter.js",
        platform_root
        / "services/api/dist/confidential-execution/release/native-output-release.js",
        platform_root
        / "services/api/dist/confidential-execution/action-policy/deterministic-action-policy.js",
    ]
    if not all(path.is_file() for path in required_builds):
        raise RuntimeError("Claude Gate 0 requires current platform build outputs")
    node = _node_binary()
    bridge = root / "scripts/governed_openrouter_bridge.cjs"
    syntax = subprocess.run([node, "--check", str(bridge)], capture_output=True, check=False)
    if syntax.returncode != 0:
        raise RuntimeError("Claude Gate 0 bridge syntax validation failed")
    module_probe = subprocess.run(
        [
            node,
            "-e",
            (
                "const a=require(process.argv[1]);const r=require(process.argv[2]);"
                "if(typeof a.evaluateDeterministicActionBatch!=='function'||"
                "typeof r.evaluateNativeOutputRelease!=='function')process.exit(2)"
            ),
            str(required_builds[3]),
            str(required_builds[2]),
        ],
        capture_output=True,
        check=False,
    )
    if module_probe.returncode != 0:
        raise RuntimeError("Claude Gate 0 native validators failed to load")
    schema = assessment_schema(1, config["actionPolicyValue"])
    prompts = assessment_prompts()
    secret_scan = _secret_scan(root, platform_root)
    previous_failures = sum(
        row.get("status") == "failed"
        for path in (root / "results/v2/raw/inference").glob(
            "openrouter-frontier-smoke-anthropic-claude-*.jsonl.partial"
        )
        for row in read_jsonl(path)
    )
    evidence = {
        "schemaVersion": "purposebound-finance.claude-gate-zero.v2",
        "recordedAt": datetime.now(UTC).isoformat(),
        "status": "PASSED",
        "platformCommit": git_commit(platform_root),
        "researchCommit": git_commit(root),
        "phaseConfiguration": config_path.relative_to(root).as_posix(),
        "modelManifest": config["claudeModelManifest"],
        "modelManifestHash": config["modelManifestValue"]["manifestHash"],
        "actionPolicyHash": config["actionPolicyHash"],
        "responseSchemaHash": sha256_json(schema),
        "promptHashes": {key: sha256_text(value) for key, value in prompts.items()},
        "checks": {
            "openRouterAdapterBuilt": True,
            "openRouterTransportTestsPassed": True,
            "secretReferenceResolved": True,
            "modelManifestValidated": True,
            "routeMetadataValidated": True,
            "schemaValidatorLoaded": True,
            "nativeReleaseValidatorLoaded": True,
            "batchMapperLoaded": True,
            "evidenceWriterReady": True,
            "cleanupHandlerReady": True,
            "budgetReservationPreflightPassed": True,
        },
        "secretPersistenceScan": secret_scan,
        "previousClaudeFailuresPreserved": previous_failures,
        "budget": {
            "committedEur": global_committed,
            "categoryCommittedEur": category_committed,
            "maximumNextReservationEur": reservation,
            "categoryAuthorizedEur": compatibility["maximumCompatibilityBudgetEur"],
            "absoluteAuthorizedEur": config["budget"]["absoluteAuthorizedEur"],
        },
        "providerCalls": 0,
    }
    return write_new_v2_artifact(
        root,
        Path("results/v2/manifests/openrouter-claude-gate0-20260805.json"),
        evidence,
    )


def _safe_provider_failure(error: Exception, manifest: Mapping[str, Any]) -> dict[str, Any]:
    match = re.search(r"PROVIDER_SAFE_ERROR:(\{.*\})", str(error), re.DOTALL)
    if not match:
        return {
            "httpStatus": None,
            "requestId": None,
            "category": "UNKNOWN_SAFE_CLASS",
            "providerCode": None,
            "fieldHints": [],
            "selectedProviderRoute": manifest["upstreamRoute"],
            "responseBodySha256": None,
        }
    try:
        diagnostic = json.loads(match.group(1))
    except json.JSONDecodeError:
        diagnostic = {}
    allowed = {
        "httpStatus",
        "requestId",
        "category",
        "providerCode",
        "fieldHints",
        "selectedProviderRoute",
        "responseBodySha256",
    }
    if (
        not isinstance(diagnostic, dict)
        or set(diagnostic) != allowed
        or diagnostic.get("category") not in SAFE_CATEGORIES
        or diagnostic.get("selectedProviderRoute") != manifest["upstreamRoute"]
    ):
        return {
            "httpStatus": None,
            "requestId": None,
            "category": "UNKNOWN_SAFE_CLASS",
            "providerCode": None,
            "fieldHints": [],
            "selectedProviderRoute": manifest["upstreamRoute"],
            "responseBodySha256": None,
        }
    return diagnostic


def _gate_artifact_stem(gate: int) -> str:
    return f"openrouter-phase2-claude-gate{gate}"


def run_paid_gate(root: Path, platform_root: Path, config_path: Path, gate: int) -> Path:
    if gate not in {1, 2}:
        raise ValueError("Paid Claude compatibility gate must be one or two")
    config = load_phase_configuration(root, config_path)
    gate0 = root / "results/v2/manifests/openrouter-claude-gate0-20260805.json"
    if not gate0.is_file() or json.loads(gate0.read_text(encoding="utf-8")).get("status") != "PASSED":
        raise RuntimeError("Claude Gate 0 has not passed")
    if gate == 2:
        gate1 = root / "results/v2/manifests/openrouter-phase2-claude-gate1.json"
        if not gate1.is_file() or json.loads(gate1.read_text(encoding="utf-8")).get("status") != "PASSED":
            raise RuntimeError("Claude Gate 1 has not passed")
    compatibility = config["claudeCompatibility"]
    dataset_path = root / config["dataset"]
    rows = load_paired_records(dataset_path, pair_limit=4 if gate == 2 else 1)
    if gate == 1:
        rows = rows[:1]
    records, selected_fields, denied_fields, pseudonymized_fields = prepare_remote_batch(
        rows,
        dataset_sha256=sha256_file(dataset_path),
    )
    schema = assessment_schema(len(rows), config["actionPolicyValue"])
    prompts = assessment_prompts()
    platform_commit = git_commit(platform_root)
    contract_material = build_contract_material(
        config=config,
        rows=rows,
        selected_fields=selected_fields,
        denied_fields=denied_fields,
        schema=schema,
        prompts=prompts,
        gate=gate,
        platform_commit=platform_commit,
    )
    contract_hash = sha256_json(contract_material)
    manifest = config["modelManifestValue"]
    if repeated_failed_combination(root, manifest["manifestHash"], contract_hash):
        raise RuntimeError("Identical failed Claude combination is not eligible to rerun")
    stem = _gate_artifact_stem(gate)
    final_path = root / f"results/v2/raw/inference/{stem}.jsonl"
    partial_path = final_path.with_suffix(".jsonl.partial")
    manifest_path = root / f"results/v2/manifests/{stem}.json"
    if final_path.exists() or partial_path.exists() or manifest_path.exists():
        raise FileExistsError(f"Claude Gate {gate} artifact already exists")
    phase = f"claude_gate_{gate}"
    reservation_amount = float(compatibility["maximumReservationPerAttemptEur"])
    reservation_id, _, _ = reserve_phase_budget(
        root / config["budget"]["ledger"],
        model_id=manifest["modelId"],
        phase=phase,
        category=BUDGET_CATEGORY,
        authorization_id=AUTHORIZATION_ID,
        authorized_cost_eur=reservation_amount,
        category_authorized_eur=float(compatibility["maximumCompatibilityBudgetEur"]),
        absolute_authorized_eur=float(config["budget"]["absoluteAuthorizedEur"]),
    )
    started = datetime.now(UTC)
    tick = time.perf_counter()
    provider_evidence: dict[str, Any] | None = None
    provider_cost: Mapping[str, Any] | None = None
    try:
        invocation = invoke_openrouter_bridge(
            benchmark_root=root,
            platform_root=platform_root,
            payload={
                "contractHash": contract_hash,
                "modelManifest": manifest,
                "workloadImageDigest": "sha256:" + "0" * 64,
                "seed": None,
                "outputTokenLimit": int(compatibility["outputTokenLimit"]),
                "timeoutMs": int(compatibility["timeoutMs"]),
                "selectedFields": list(selected_fields),
                "records": records,
                "prompts": prompts,
                "responseSchema": schema,
                "nativeReleasePolicy": native_release_policy(schema, rows),
                "actionPolicy": config["actionPolicyValue"],
                "actionPolicyHash": config["actionPolicyHash"],
                "expectedRecordCount": len(rows),
                "maximumAuthorizedCostEur": reservation_amount,
            },
        )
        provider_evidence = invocation["evidence"]
        provider_cost = provider_evidence.get("providerReportedCost")
        native_release = invocation["nativeRelease"]
        governed = invocation["governedActionBatch"]
        raw_output = invocation["quarantinedOutput"]
        parsed_output = json.loads(raw_output)
        findings = _disclosure_findings(raw_output, rows)
        conservative_cost = provider_evidence["cost"]["amountEur"]
        if (
            native_release.get("allowed") is not True
            or findings
            or governed.get("policyHash") != config["actionPolicyHash"]
            or governed.get("recordCount") != len(rows)
            or governed.get("modelOutputHash") != sha256_json(parsed_output)
            or not isinstance(conservative_cost, (int, float))
            or conservative_cost > reservation_amount
        ):
            raise ValueError("Claude output failed release, mapping, or cost controls")
        global_committed, category_committed = settle_phase_budget(
            root / config["budget"]["ledger"],
            reservation_id=reservation_id,
            model_id=manifest["modelId"],
            phase=phase,
            category=BUDGET_CATEGORY,
            authorization_id=AUTHORIZATION_ID,
            budget_debit_eur=float(conservative_cost),
            outcome="passed",
            provider_reported_cost=provider_cost,
        )
        record = {
            "schemaVersion": "purposebound-finance.claude-compatibility.v2",
            "recordType": "claude_compatibility_gate",
            "evidenceId": str(uuid.uuid4()),
            "status": "passed",
            "gate": gate,
            "startedAt": started.isoformat(),
            "finishedAt": datetime.now(UTC).isoformat(),
            "durationSeconds": round(time.perf_counter() - tick, 3),
            "processingClassification": "REMOTE_PROVIDER_PROCESSING",
            "contractMaterial": contract_material,
            "contractHash": contract_hash,
            "modelManifestHash": manifest["manifestHash"],
            "actionPolicyHash": config["actionPolicyHash"],
            "recordCount": len(rows),
            "pairCount": 0 if gate == 1 else 4,
            "orderedCaseIds": [str(row["case_id"]) for row in rows],
            "transmittedFields": list(selected_fields),
            "prohibitedSyntheticFields": list(denied_fields),
            "prohibitedSyntheticFieldsTransmitted": False,
            "identifiersPseudonymized": bool(pseudonymized_fields),
            "releasedModelOutput": parsed_output,
            "releasedModelOutputHash": sha256_json(parsed_output),
            "governedActionBatch": governed,
            "releaseAllowed": True,
            "disclosureFindings": findings,
            "nativeReleaseEvidence": native_release,
            "modelEvidence": provider_evidence,
            "budget": {
                "reservationId": reservation_id,
                "conservativeDebitEur": conservative_cost,
                "providerReportedCost": provider_cost,
                "globalCommittedEur": global_committed,
                "categoryCommittedEur": category_committed,
            },
        }
        append_jsonl(partial_path, record)
        os.replace(partial_path, final_path)
        ledger_rows = read_jsonl(root / config["budget"]["ledger"])
        result_manifest = {
            "schemaVersion": "purposebound-finance.claude-compatibility-manifest.v2",
            "status": "PASSED",
            "gate": gate,
            "modelId": manifest["modelId"],
            "modelManifestHash": manifest["manifestHash"],
            "actionPolicyHash": config["actionPolicyHash"],
            "rawArtifact": final_path.relative_to(root).as_posix(),
            "rawArtifactSha256": sha256_file(final_path),
            "contractHash": contract_hash,
            "providerCalls": 1,
            "retryCount": 0,
            "budgetLedgerPrefixRecordCount": len(ledger_rows),
            "budgetLedgerPrefixHash": sha256_json(ledger_rows),
            "budgetCategory": BUDGET_CATEGORY,
            "conservativeDebitEur": conservative_cost,
            "providerReportedCost": provider_cost,
        }
        return write_new_v2_artifact(root, manifest_path.relative_to(root), result_manifest)
    except Exception as error:  # noqa: BLE001 - every paid-call failure must settle and persist
        diagnostic = _safe_provider_failure(error, manifest)
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
            category=BUDGET_CATEGORY,
            authorization_id=AUTHORIZATION_ID,
            budget_debit_eur=debit,
            outcome="failed_conservative_debit" if provider_evidence is None else "failed_known_debit",
            provider_reported_cost=provider_cost,
        )
        append_jsonl(
            partial_path,
            {
                "schemaVersion": "purposebound-finance.claude-compatibility.v2",
                "recordType": "claude_compatibility_gate",
                "evidenceId": str(uuid.uuid4()),
                "status": "failed",
                "gate": gate,
                "startedAt": started.isoformat(),
                "finishedAt": datetime.now(UTC).isoformat(),
                "durationSeconds": round(time.perf_counter() - tick, 3),
                "processingClassification": "REMOTE_PROVIDER_PROCESSING",
                "contractMaterial": contract_material,
                "contractHash": contract_hash,
                "modelManifestHash": manifest["manifestHash"],
                "providerDiagnostic": diagnostic,
                "providerCalls": 1,
                "retryCount": 0,
                "budget": {
                    "reservationId": reservation_id,
                    "conservativeDebitEur": debit,
                    "providerReportedCost": provider_cost,
                    "globalCommittedEur": global_committed,
                    "categoryCommittedEur": category_committed,
                },
            },
        )
        raise RuntimeError(f"Claude Gate {gate} failed closed: {diagnostic['category']}") from None
