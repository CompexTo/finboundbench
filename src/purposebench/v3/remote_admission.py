"""Frozen, capped R0 admission gate for exact OpenRouter model lanes.

One governed smoke call per candidate. Every call is budget-reserved before
transport and settled after the attempt, including failures. Raw events are
append-only and hash-chained. This phase is an admission diagnostic; it makes
no confirmatory research claim.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from purposebench.utils import (
    append_jsonl,
    canonical_json,
    git_commit,
    git_provenance,
    read_jsonl,
    sha256_file,
    sha256_json,
)
from purposebench.v3.budget import (
    LEDGER_PATH,
    committed_budget_eur,
    reserve_budget,
    settle_budget,
)

ADMISSION_LABEL = "OPENROUTER_R0_ADMISSION_DIAGNOSTIC_NOT_CONFIRMATORY"
CONFIG_PATH = Path("configs/v3/openrouter-model-admission-v3.yaml")
BRIDGE_PATH = Path("scripts/governed_openrouter_bridge_v3.cjs")
V2_BRIDGE_PATH = Path("scripts/governed_openrouter_bridge.cjs")
RESEARCH_ARTIFACTS = (
    CONFIG_PATH,
    BRIDGE_PATH,
    V2_BRIDGE_PATH,
    Path("scripts/capture_v3_openrouter_manifests.py"),
    Path("src/purposebench/v3/openrouter_metadata.py"),
    Path("src/purposebench/v3/budget.py"),
    Path("src/purposebench/v3/remote_admission.py"),
    Path("scripts/build_v3_openrouter_admission_freeze.py"),
    Path("scripts/run_v3_openrouter_admission.py"),
    Path("scripts/verify_v3_openrouter_admission.py"),
)
PLATFORM_ARTIFACTS = (
    Path("packages/types/src/confidential-execution.ts"),
    Path("services/runner/src/providers/openrouter.adapter.ts"),
    Path("services/runner/src/providers/commercial-model-adapter.ts"),
    Path("services/api/src/confidential-execution/release/native-output-release.ts"),
)
FORBIDDEN_SECRET_MARKERS = (
    "OPENROUTER_API_KEY",
    "sk-or-v1-",
    "authorization: bearer",
)
MUTABLE_ALIAS = re.compile(
    r"(?:^|[-_.:/@])(latest|current|default|stable|preview|auto)(?:$|[-_.:/@])",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_config(root: Path) -> dict[str, Any]:
    value = yaml.safe_load((root / CONFIG_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("OpenRouter admission config must be a mapping")
    return value


def _safe_path(root: Path, relative: str, expected_parent: Path) -> Path:
    candidate = (root / relative).resolve()
    allowed = (root / expected_parent).resolve()
    if candidate != allowed and allowed not in candidate.parents:
        raise ValueError(f"path escaped {expected_parent}: {relative}")
    return candidate


def _validate_manifest(value: dict[str, Any], model: dict[str, Any]) -> None:
    if value.get("schemaVersion") != "purposebound-finance.openrouter-model-manifest.v3":
        raise ValueError("unexpected OpenRouter manifest schema")
    manifest_hash = value.get("manifestHash")
    core = {key: item for key, item in value.items() if key != "manifestHash"}
    if not isinstance(manifest_hash, str) or sha256_json(core) != manifest_hash:
        raise ValueError("OpenRouter manifest hash mismatch")
    if manifest_hash != model.get("expected_manifest_hash"):
        raise ValueError("configured OpenRouter manifest hash mismatch")
    if value.get("modelId") != model.get("expected_model_id"):
        raise ValueError("configured OpenRouter model identity mismatch")
    if value.get("modelVersion") != value.get("modelId"):
        raise ValueError("OpenRouter model version is not pinned to the exact ID")
    if value.get("upstreamRoute") != model.get("expected_upstream_route"):
        raise ValueError("configured OpenRouter route mismatch")
    if MUTABLE_ALIAS.search(str(value.get("modelId", ""))):
        raise ValueError("mutable OpenRouter model alias is prohibited")
    if (
        value.get("gateway") != "OPENROUTER"
        or value.get("fallbackAllowed") is not False
        or value.get("zeroDataRetentionRequired") is not True
        or value.get("providerDataCollectionAllowed") is not False
        or value.get("structuredOutputMode") != "JSON_SCHEMA_STRICT"
        or value.get("reasoningSetting") != "DISABLED"
    ):
        raise ValueError("OpenRouter manifest routing or privacy binding is invalid")


def validate_remote_admission_config(root: Path, config: dict[str, Any]) -> None:
    """Fail closed before any paid provider process can be invoked."""

    exact = {
        "schema_version": "finboundbench.openrouter-model-admission.v3",
        "scope": "OPENROUTER_R0_SCHEMA_ROUTE_NO_FALLBACK_COST_GATE_NOT_CONFIRMATORY",
        "phase": "R0",
        "calls_per_candidate": 1,
        "paid_secrets_permitted": True,
        "secret_source": "ENVIRONMENT_REFERENCE_ONLY",
        "aws_actions_permitted": False,
        "confirmatory_claims_permitted": False,
        "hardware_attestation": False,
        "host_trust_required": True,
        "automatic_retries": 0,
        "fallback_permitted": False,
    }
    for key, expected in exact.items():
        if config.get(key) != expected:
            raise ValueError(f"unsafe or invalid OpenRouter admission setting: {key}")
    for key, low, high in (
        ("output_token_limit", 1, 4096),
        ("timeout_ms", 1, 86_400_000),
    ):
        value = config.get(key)
        if not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"invalid OpenRouter admission bound: {key}")
    expected_bridge_digest = f"sha256:{sha256_file(root / BRIDGE_PATH)}"
    if config.get("workload_image_digest") != expected_bridge_digest:
        raise ValueError("bridge source changed without updating workload digest")
    if config.get("workload_digest_semantics") != (
        "SHA256_OF_HOST_BRIDGE_SOURCE_NOT_A_CONTAINER_OR_ATTESTATION"
    ):
        raise ValueError("workload digest semantics became ambiguous")
    budget = config.get("budget")
    if not isinstance(budget, dict):
        raise TypeError("budget must be a mapping")
    if budget.get("ledger_path") != LEDGER_PATH.as_posix():
        raise ValueError("budget ledger path changed")
    reservation = float(budget.get("reservation_per_call_eur", 0))
    phase_cap = float(budget.get("phase_authorized_eur", 0))
    absolute_cap = float(budget.get("absolute_authorized_eur", 0))
    if not 0 < reservation <= phase_cap <= absolute_cap <= 1.0:
        raise ValueError("R0 budget envelope is invalid or exceeds the recorded authorization")
    if not isinstance(budget.get("authorization_id"), str) or not budget["authorization_id"]:
        raise ValueError("budget authorization ID is missing")
    if budget.get("authorization_basis") != "USER_INSTRUCTION_2026_08_05_USE_OPENROUTER_MODELS":
        raise ValueError("budget authorization basis is not the recorded user instruction")
    selected = config.get("selected_fields")
    denied = config.get("denied_fields")
    records = config.get("records")
    if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected):
        raise ValueError("selected fields must be a unique nonempty list")
    if not isinstance(denied, list) or set(selected) & set(denied):
        raise ValueError("selected and denied fields overlap")
    if not isinstance(records, list) or len(records) != 1 or set(records[0]) != set(selected):
        raise ValueError("admission record is not an exact approved projection")
    projected = canonical_json(records)
    if any(str(value) in projected for value in config.get("prohibited_exact_values", [])):
        raise ValueError("prohibited exact value entered the admission projection")
    if any(str(field) in projected for field in denied):
        raise ValueError("denied field entered the admission projection")
    if not isinstance(config.get("prompts"), dict) or set(config["prompts"]) != {"system", "user"}:
        raise TypeError("prompts must contain exactly system and user")
    if not isinstance(config.get("response_schema"), dict):
        raise TypeError("response schema must be a mapping")
    models = config.get("models")
    if not isinstance(models, list) or len(models) != config["remote_provider_calls_permitted"]:
        raise ValueError("model lanes must equal the exact permitted call count")
    lane_ids = [model.get("lane_id") for model in models]
    if len(set(lane_ids)) != len(lane_ids):
        raise ValueError("OpenRouter lane IDs must be unique")
    for model in models:
        manifest_path = _safe_path(
            root, str(model.get("manifest_path", "")), Path("docs/v3/model-manifests")
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_manifest(manifest, model)
    claude = config.get("claude_lane")
    if not isinstance(claude, dict) or claude.get("admission") != "EXCLUDED_FROM_R0":
        raise ValueError("Claude exclusion record changed")


def native_release_policy(config: dict[str, Any]) -> dict[str, Any]:
    required = [
        "compex.output.json-schema",
        "compex.output.required-fields",
        "compex.output.decision-vocabulary",
        "compex.output.numeric-bounds",
        "compex.output.max-bytes",
        "compex.output.prohibited-exact-values",
        "compex.output.prohibited-field-names",
        "compex.output.pii-patterns",
        "compex.output.artifact-type",
        "compex.output.model-release",
    ]
    return {
        "policyRuleId": "finboundbench-v3-r0-admission-release",
        "requiredValidators": required,
        "jsonSchema": {"schema": config["response_schema"]},
        "requiredFields": {"paths": ["/decision", "/score", "/reason"]},
        "decisionVocabulary": {
            "path": "/decision",
            "permittedValues": ["STANDARD_QUEUE", "PRIORITY_QUEUE"],
        },
        "numericBounds": {
            "bounds": [{"path": "/score", "minimum": 0, "maximum": 100, "integer": True}]
        },
        "maxBytes": {"maximumBytes": 8192},
        "prohibitedExactValues": {"values": config["prohibited_exact_values"]},
        "prohibitedFieldNames": {"names": config["denied_fields"], "caseInsensitive": True},
        "piiPatterns": {"patterns": ["EMAIL", "US_SSN", "IBAN", "CREDIT_CARD"]},
        "artifactType": {"permittedTypes": ["application/json"]},
        "modelRelease": {"permitted": False},
    }


def build_bridge_payload(config: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    material = {
        "admissionId": config["admission_id"],
        "model": model["expected_model_id"],
        "route": model["expected_upstream_route"],
        "selectedFields": config["selected_fields"],
        "recordsHash": sha256_json(config["records"]),
        "promptsHash": sha256_json(config["prompts"]),
        "responseSchemaHash": sha256_json(config["response_schema"]),
        "releasePolicyHash": sha256_json(native_release_policy(config)),
        "seed": config["seed"],
    }
    return {
        "contractHash": sha256_json(material),
        "manifestRelativePath": model["manifest_path"],
        "workloadImageDigest": config["workload_image_digest"],
        "seed": config["seed"],
        "outputTokenLimit": config["output_token_limit"],
        "timeoutMs": config["timeout_ms"],
        "selectedFields": config["selected_fields"],
        "records": config["records"],
        "prompts": config["prompts"],
        "responseSchema": config["response_schema"],
        "nativeReleasePolicy": native_release_policy(config),
        "maximumAuthorizedCostEur": float(config["budget"]["reservation_per_call_eur"]),
    }


def _artifact(root: Path, path: Path, repository: str) -> dict[str, Any]:
    absolute = root / path
    return {
        "repository": repository,
        "path": path.as_posix(),
        "sha256": sha256_file(absolute),
        "bytes": absolute.stat().st_size,
    }


def model_manifest_artifacts(root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _artifact(root, Path(model["manifest_path"]), "research")
        for model in config["models"]
    ]


def build_remote_admission_freeze(
    research_root: Path,
    platform_root: Path,
    *,
    research_commit: str,
    platform_commit: str,
) -> dict[str, Any]:
    config = _read_config(research_root)
    validate_remote_admission_config(research_root, config)
    artifacts = [
        *(_artifact(research_root, path, "research") for path in RESEARCH_ARTIFACTS),
        *model_manifest_artifacts(research_root, config),
        *(_artifact(platform_root, path, "platform") for path in PLATFORM_ARTIFACTS),
    ]
    core = {
        "schemaVersion": "finboundbench.openrouter-admission-freeze.v3",
        "admissionId": config["admission_id"],
        "scope": config["scope"],
        "status": "FROZEN_R0_ADMISSION_ONLY",
        "frozenAt": _now(),
        "repositoryBindings": {
            "researchCommit": research_commit,
            "platformCommit": platform_commit,
        },
        "repositoryStateAtFreeze": {
            "research": git_provenance(research_root),
            "platform": git_provenance(platform_root),
            "platformScopeBoundByArtifactHashes": True,
            "unrelatedUserChangesIncluded": False,
        },
        "remoteProviderCallsPermitted": config["remote_provider_calls_permitted"],
        "providerSecretPermitted": True,
        "secretSource": "ENVIRONMENT_REFERENCE_ONLY",
        "awsActionsPermitted": False,
        "confirmatoryClaimsPermitted": False,
        "hardwareAttestation": False,
        "budget": {
            "ledgerPath": config["budget"]["ledger_path"],
            "authorizationId": config["budget"]["authorization_id"],
            "authorizationBasis": config["budget"]["authorization_basis"],
            "reservationPerCallEur": float(config["budget"]["reservation_per_call_eur"]),
            "phaseAuthorizedEur": float(config["budget"]["phase_authorized_eur"]),
            "absoluteAuthorizedEur": float(config["budget"]["absolute_authorized_eur"]),
        },
        "modelManifestHashes": [
            model["expected_manifest_hash"] for model in config["models"]
        ],
        "artifacts": artifacts,
    }
    return {**core, "freezeManifestHash": sha256_json(core)}


def _is_ancestor(root: Path, ancestor: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
    ).returncode == 0


def verify_remote_admission_freeze(
    research_root: Path, platform_root: Path
) -> dict[str, Any]:
    config = _read_config(research_root)
    validate_remote_admission_config(research_root, config)
    path = research_root / config["freeze_manifest_path"]
    value = json.loads(path.read_text(encoding="utf-8"))
    claimed_hash = value.pop("freezeManifestHash", None)
    if not isinstance(claimed_hash, str) or sha256_json(value) != claimed_hash:
        raise ValueError("OpenRouter admission freeze self-hash mismatch")
    value["freezeManifestHash"] = claimed_hash
    bindings = value["repositoryBindings"]
    if not _is_ancestor(research_root, bindings["researchCommit"]):
        raise ValueError("frozen research commit is not an ancestor of HEAD")
    if not _is_ancestor(platform_root, bindings["platformCommit"]):
        raise ValueError("frozen platform commit is not an ancestor of HEAD")
    roots = {"research": research_root, "platform": platform_root}
    for artifact in value["artifacts"]:
        artifact_path = roots[artifact["repository"]] / artifact["path"]
        if artifact_path.stat().st_size != artifact["bytes"] or sha256_file(
            artifact_path
        ) != artifact["sha256"]:
            raise ValueError(f"frozen artifact changed: {artifact['path']}")
    return value


def _append_chained(path: Path, core: dict[str, Any], previous: str) -> str:
    event = {**core, "previousEventHash": previous}
    event_hash = sha256_json(event)
    append_jsonl(path, {**event, "eventHash": event_hash})
    return event_hash


def run_remote_model_admission(
    research_root: Path, platform_root: Path
) -> dict[str, Any]:
    freeze = verify_remote_admission_freeze(research_root, platform_root)
    config = _read_config(research_root)
    raw_path = research_root / config["raw_events_path"]
    manifest_path = research_root / config["run_manifest_path"]
    if raw_path.exists() or manifest_path.exists():
        raise FileExistsError("R0 admission results already exist; append-only run will not overwrite")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path = research_root / config["budget"]["ledger_path"]
    if ledger_path.exists() and read_jsonl(ledger_path):
        raise FileExistsError("R0 ledger already has records; refusing to mix phases")
    budget = config["budget"]
    previous = "0" * 64
    attempts = 0
    admitted = 0
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    environment["FINBOUNDBENCH_ROOT"] = str(research_root)
    for sequence, model in enumerate(config["models"], start=1):
        attempts += 1
        payload = build_bridge_payload(config, model)
        started_at = _now()
        reservation_id = reserve_budget(
            ledger_path,
            model_id=model["expected_model_id"],
            phase=config["phase"],
            authorization_id=budget["authorization_id"],
            authorized_cost_eur=float(budget["reservation_per_call_eur"]),
            phase_authorized_eur=float(budget["phase_authorized_eur"]),
            absolute_authorized_eur=float(budget["absolute_authorized_eur"]),
        )
        provider_reported_cost: dict[str, Any] | None = None
        try:
            completed = subprocess.run(
                ["node", str(research_root / BRIDGE_PATH)],
                input=canonical_json(payload),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=(config["timeout_ms"] // 1000) + 120,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or f"bridge exit {completed.returncode}")
            result = json.loads(completed.stdout)
            released = bool(result.get("nativeRelease", {}).get("allowed"))
            evidence = result.get("evidence", {})
            provider_reported_cost = evidence.get("providerReportedCost")
            calculated = evidence.get("cost", {})
            debit = float(
                calculated.get("amountEur")
                if calculated.get("amountEur") is not None
                else budget["reservation_per_call_eur"]
            )
            if released:
                admitted += 1
            outcome = {
                "status": "ADMITTED" if released else "RELEASE_DENIED",
                "result": result,
                "errorClass": None,
                "errorMessage": None,
            }
            settle_budget(
                ledger_path,
                reservation_id=reservation_id,
                model_id=model["expected_model_id"],
                phase=config["phase"],
                authorization_id=budget["authorization_id"],
                budget_debit_eur=min(debit, float(budget["reservation_per_call_eur"])),
                outcome="passed" if released else "release_denied",
                provider_reported_cost=provider_reported_cost,
            )
        except Exception as error:  # every failure must become append-only evidence
            outcome = {
                "status": "FAILED",
                "result": None,
                "errorClass": type(error).__name__,
                "errorMessage": str(error)[:2000],
            }
            settle_budget(
                ledger_path,
                reservation_id=reservation_id,
                model_id=model["expected_model_id"],
                phase=config["phase"],
                authorization_id=budget["authorization_id"],
                budget_debit_eur=float(budget["reservation_per_call_eur"]),
                outcome="failed_conservative_debit",
                provider_reported_cost=provider_reported_cost,
            )
        previous = _append_chained(
            raw_path,
            {
                "schemaVersion": "finboundbench.openrouter-admission-event.v3",
                "admissionLabel": ADMISSION_LABEL,
                "sequence": sequence,
                "laneId": model["lane_id"],
                "expectedModelId": model["expected_model_id"],
                "expectedUpstreamRoute": model["expected_upstream_route"],
                "expectedManifestHash": model["expected_manifest_hash"],
                "contractHash": payload["contractHash"],
                "projectionHash": sha256_json(config["records"]),
                "selectedFields": config["selected_fields"],
                "reservationId": reservation_id,
                "remoteProviderCalls": 1,
                "paidSecretRead": True,
                "awsActions": 0,
                "hardwareAttestation": False,
                "hostTrustRequired": True,
                "automaticRetries": 0,
                "fallbackUsed": False,
                "startedAt": started_at,
                "completedAt": _now(),
                **outcome,
            },
            previous,
        )
    raw_artifact = {
        "path": config["raw_events_path"],
        "sha256": sha256_file(raw_path),
        "bytes": raw_path.stat().st_size,
        "events": attempts,
    }
    ledger_rows = read_jsonl(ledger_path)
    core = {
        "schemaVersion": "finboundbench.openrouter-admission-run.v3",
        "admissionLabel": ADMISSION_LABEL,
        "admissionId": config["admission_id"],
        "status": (
            "PASSED_R0_ADMISSION" if admitted == attempts else "COMPLETED_WITH_RETAINED_FAILURES"
        ),
        "freezeManifestHash": freeze["freezeManifestHash"],
        "repositoryBindings": freeze["repositoryBindings"],
        "attempts": attempts,
        "admitted": admitted,
        "failedOrDenied": attempts - admitted,
        "finalEventHash": previous,
        "rawArtifact": raw_artifact,
        "budget": {
            "ledgerPath": config["budget"]["ledger_path"],
            "ledgerRecordCount": len(ledger_rows),
            "ledgerHash": sha256_json(ledger_rows),
            "committedEur": committed_budget_eur(ledger_rows),
            "phaseAuthorizedEur": float(budget["phase_authorized_eur"]),
            "absoluteAuthorizedEur": float(budget["absolute_authorized_eur"]),
        },
        "remoteProviderCalls": attempts,
        "paidSecretReads": True,
        "awsActions": 0,
        "hardwareAttestation": False,
        "hostTrustRequired": True,
        "confirmatoryClaimsPermitted": False,
        "completedAt": _now(),
    }
    manifest = {**core, "manifestHash": sha256_json(core)}
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return verify_remote_model_admission(research_root, platform_root)


def verify_remote_model_admission(
    research_root: Path, platform_root: Path
) -> dict[str, Any]:
    freeze = verify_remote_admission_freeze(research_root, platform_root)
    config = _read_config(research_root)
    manifest_path = research_root / config["run_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed = manifest.pop("manifestHash", None)
    if not isinstance(claimed, str) or sha256_json(manifest) != claimed:
        raise ValueError("R0 admission run manifest self-hash mismatch")
    manifest["manifestHash"] = claimed
    if manifest["freezeManifestHash"] != freeze["freezeManifestHash"]:
        raise ValueError("R0 admission run is not bound to the active freeze")
    raw_path = research_root / manifest["rawArtifact"]["path"]
    if sha256_file(raw_path) != manifest["rawArtifact"]["sha256"]:
        raise ValueError("R0 admission raw artifact hash mismatch")
    events = read_jsonl(raw_path)
    if len(events) != manifest["attempts"] or len(events) != len(config["models"]):
        raise ValueError("R0 admission event count mismatch")
    ledger_path = research_root / config["budget"]["ledger_path"]
    ledger_rows = read_jsonl(ledger_path)
    if len(ledger_rows) != manifest["budget"]["ledgerRecordCount"] or sha256_json(
        ledger_rows
    ) != manifest["budget"]["ledgerHash"]:
        raise ValueError("R0 admission budget ledger changed after the run")
    if committed_budget_eur(ledger_rows) != manifest["budget"]["committedEur"]:
        raise ValueError("R0 admission committed budget mismatch")
    if committed_budget_eur(ledger_rows) > float(config["budget"]["absolute_authorized_eur"]):
        raise ValueError("R0 admission exceeded the absolute authorization")
    reservations = {
        row["reservationId"]
        for row in ledger_rows
        if row.get("recordType") == "budget_reservation"
    }
    settlements = {
        row["reservationId"]
        for row in ledger_rows
        if row.get("recordType") == "budget_settlement"
    }
    if reservations != settlements or len(reservations) != len(events):
        raise ValueError("R0 admission reservations are not completely settled")
    previous = "0" * 64
    admitted = 0
    for sequence, (event, model) in enumerate(zip(events, config["models"], strict=True), start=1):
        event_hash = event.pop("eventHash", None)
        if event.get("previousEventHash") != previous or sha256_json(event) != event_hash:
            raise ValueError("R0 admission event chain mismatch")
        event["eventHash"] = event_hash
        previous = event_hash
        if event["sequence"] != sequence or event["laneId"] != model["lane_id"]:
            raise ValueError("R0 admission lane ordering mismatch")
        if any(
            (
                event["remoteProviderCalls"] != 1,
                event["paidSecretRead"] is not True,
                event["awsActions"] != 0,
                event["hardwareAttestation"],
                event["automaticRetries"] != 0,
                event["fallbackUsed"],
            )
        ):
            raise ValueError("R0 admission safety invariant failed")
        if event["status"] == "ADMITTED":
            result = event["result"]
            evidence = result["evidence"]
            release = result["nativeRelease"]
            if evidence["modelId"] != model["expected_model_id"]:
                raise ValueError("observed OpenRouter model identity mismatch")
            if evidence["destinationHost"] != "openrouter.ai":
                raise ValueError("observed OpenRouter destination mismatch")
            if evidence["processingClassification"] != "REMOTE_PROVIDER_PROCESSING":
                raise ValueError("processing classification is not remote")
            if evidence["contractHash"] != event["contractHash"]:
                raise ValueError("R0 evidence contract mismatch")
            if evidence["transmittedFields"] != config["selected_fields"]:
                raise ValueError("R0 evidence projection mismatch")
            if evidence["attemptCount"] != 1:
                raise ValueError("R0 evidence shows a retry")
            if not release["allowed"] or any(
                item["decision"] == "DENY" for item in release["events"]
            ):
                raise ValueError("admitted lane did not pass native release")
            parsed = json.loads(result["quarantinedOutput"])
            if parsed.get("decision") not in ("STANDARD_QUEUE", "PRIORITY_QUEUE"):
                raise ValueError("admitted lane returned an invalid decision")
            admitted += 1
    if previous != manifest["finalEventHash"] or admitted != manifest["admitted"]:
        raise ValueError("R0 admission summary mismatch")
    text = raw_path.read_text(encoding="utf-8").lower()
    if any(marker.lower() in text for marker in FORBIDDEN_SECRET_MARKERS):
        raise ValueError("provider secret marker found in R0 admission evidence")
    return manifest


def current_repository_bindings(research_root: Path, platform_root: Path) -> dict[str, str]:
    return {"researchCommit": git_commit(research_root), "platformCommit": git_commit(platform_root)}
