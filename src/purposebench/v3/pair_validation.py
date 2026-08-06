"""One-pair B0/P3 validation gate for the v3 purpose-selective benchmark.

Four paid executions: HMDA first pair, conditions B0 (full record) and P3
(approved fields only), each over variants A and B. The pair bridge forwards
the approved/prohibited partition to the platform adapter, so every event
carries per-partition payload hashes. Verification fails closed unless:

- variant A and B transmitted identical approved projections (same
  ``approvedPayloadHash``) in every condition;
- the full-record condition differs between variants only in prohibited
  fields (``prohibitedPayloadHash`` differs, full ``payloadHash`` differs),
  while the approved-only condition is byte-identical across variants;
- the model's routing decision matches the deterministic ground truth;
- every reservation is settled and the absolute authorization is respected.

This gate is a validation diagnostic; it makes no confirmatory research claim.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
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
    committed_budget_eur,
    reserve_budget,
    settle_budget,
)
from purposebench.v3.remote_admission import (
    FORBIDDEN_SECRET_MARKERS,
    _is_ancestor,
    _safe_path,
    _validate_manifest,
)
from purposebench.v3.tasks import (
    PRIORITY_REVIEW,
    STANDARD_REVIEW,
    hmda_review_routing_ground_truth,
)
from purposebench.v3.transmission import (
    classify_projection,
    projection_payload_hash,
)

VALIDATION_LABEL = "OPENROUTER_ONE_PAIR_VALIDATION_GATE_NOT_CONFIRMATORY"
CONFIG_PATH = Path("configs/v3/openrouter-one-pair-validation.yaml")
BRIDGE_PATH = Path("scripts/governed_openrouter_pair_bridge_v3.cjs")
RESEARCH_ARTIFACTS = (
    CONFIG_PATH,
    BRIDGE_PATH,
    Path("src/purposebench/v3/pair_validation.py"),
    Path("src/purposebench/v3/tasks.py"),
    Path("src/purposebench/v3/transmission.py"),
    Path("src/purposebench/v3/budget.py"),
    Path("src/purposebench/v3/remote_admission.py"),
    Path("src/purposebench/v3/openrouter_metadata.py"),
    Path("scripts/build_v3_one_pair_freeze.py"),
    Path("scripts/run_v3_one_pair_validation.py"),
    Path("scripts/verify_v3_one_pair_validation.py"),
)
PLATFORM_ARTIFACTS = (
    Path("packages/types/src/confidential-execution.ts"),
    Path("services/runner/src/providers/openrouter.adapter.ts"),
    Path("services/runner/src/providers/commercial-model-adapter.ts"),
    Path("services/api/src/confidential-execution/release/native-output-release.ts"),
)
ALL_RECORD_FIELDS = "ALL_RECORD_FIELDS"
APPROVED_FIELDS_ONLY = "APPROVED_FIELDS_ONLY"
DECISION_VOCABULARY = (PRIORITY_REVIEW, STANDARD_REVIEW)
NODE_MIN_MAJOR = 22


@dataclass(frozen=True)
class Cell:
    condition: str
    variant: str
    pair_id: str
    selected_fields: tuple[str, ...]
    approved_fields: tuple[str, ...]
    prohibited_fields: tuple[str, ...]
    dataset_prohibited_fields: tuple[str, ...]
    records: tuple[dict[str, Any], ...]
    ground_truth: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_config(root: Path) -> dict[str, Any]:
    value = yaml.safe_load((root / CONFIG_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("one-pair validation config must be a mapping")
    return value


def _validate_model_lanes(root: Path, config: dict[str, Any]) -> None:
    models = config.get("models")
    if not isinstance(models, list) or len(models) != 1:
        raise ValueError("one-pair validation requires exactly one pinned model lane")
    for model in models:
        manifest_path = _safe_path(
            root, str(model.get("manifest_path", "")), Path("docs/v3/model-manifests")
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_manifest(manifest, model)


def _validate_task(root: Path, config: dict[str, Any]) -> None:
    task = config.get("task")
    if not isinstance(task, dict):
        raise TypeError("task must be a mapping")
    if task.get("ground_truth") != "hmda_review_routing_ground_truth":
        raise ValueError("task ground truth is not the pinned HMDA router")
    if task.get("dataset") != "hmda":
        raise ValueError("task dataset is not hmda")
    if task.get("labels") != list(DECISION_VOCABULARY):
        raise ValueError("task labels changed")
    pairs = task.get("pairs")
    if not isinstance(pairs, list) or not pairs or any(not isinstance(p, str) for p in pairs):
        raise ValueError("task pairs must be a nonempty list of pair ids")
    pair_file = _safe_path(root, str(task.get("pair_file", "")), Path("data/v2/generated"))
    if not pair_file.is_file():
        raise ValueError("task pair file does not exist")
    available: set[str] = set()
    for line in pair_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        variants = row.get("variant")
        if row.get("dataset_id") == "hmda" and variants in ("A", "B"):
            available.add(str(row["pair_id"]))
    for pair_id in pairs:
        if pair_id not in available:
            raise ValueError(f"configured pair is not available with both variants: {pair_id}")


def _validate_denied_fields(root: Path, config: dict[str, Any]) -> None:
    pair_file = _safe_path(root, str(config["task"]["pair_file"]), Path("data/v2/generated"))
    expected: set[str] = set()
    for line in pair_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("pair_id") in config["task"]["pairs"]:
            expected |= set(row.get("prohibited_internal_fields", []))
    denied = config.get("denied_fields")
    if not isinstance(denied, list) or sorted(denied) != sorted(expected):
        raise ValueError("denied fields must equal the dataset's prohibited fields")


def _validate_conditions(config: dict[str, Any]) -> None:
    conditions = config.get("conditions")
    if not isinstance(conditions, list) or [c.get("name") for c in conditions] != ["B0", "P3"]:
        raise ValueError("conditions must be exactly [B0, P3] in order")
    if {c.get("transmit") for c in conditions} != {ALL_RECORD_FIELDS, APPROVED_FIELDS_ONLY}:
        raise ValueError("conditions must use the two pinned transmission rules")


def validate_pair_validation_config(root: Path, config: dict[str, Any]) -> None:
    """Fail closed before any paid provider process can be invoked."""
    exact = {
        "schema_version": "finboundbench.openrouter-pair-validation.v3",
        "scope": "OPENROUTER_ONE_PAIR_VALIDATION",
        "phase": "ONE_PAIR_VALIDATION",
        "calls_per_candidate": 1,
        "remote_provider_calls_permitted": 4,
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
            raise ValueError(f"unsafe or invalid one-pair validation setting: {key}")
    for key, low, high in (
        ("output_token_limit", 1, 4096),
        ("timeout_ms", 1, 86_400_000),
    ):
        value = config.get(key)
        if not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"invalid one-pair validation bound: {key}")
    expected_bridge_digest = f"sha256:{sha256_file(root / BRIDGE_PATH)}"
    if config.get("workload_image_digest") != expected_bridge_digest:
        raise ValueError("pair bridge source changed without updating workload digest")
    if config.get("workload_digest_semantics") != (
        "SHA256_OF_HOST_BRIDGE_SOURCE_NOT_A_CONTAINER_OR_ATTESTATION"
    ):
        raise ValueError("workload digest semantics became ambiguous")
    budget = config.get("budget")
    if not isinstance(budget, dict):
        raise TypeError("budget must be a mapping")
    reservation = float(budget.get("reservation_per_call_eur", 0))
    phase_cap = float(budget.get("phase_authorized_eur", 0))
    absolute_cap = float(budget.get("absolute_authorized_eur", 0))
    if not 0 < reservation <= phase_cap <= absolute_cap <= 1.0:
        raise ValueError("one-pair validation budget envelope is invalid or exceeds the authorization")
    if not isinstance(budget.get("authorization_id"), str) or not budget["authorization_id"]:
        raise ValueError("budget authorization ID is missing")
    if budget.get("authorization_basis") != "USER_INSTRUCTION_2026_08_05_USE_OPENROUTER_MODELS":
        raise ValueError("budget authorization basis is not the recorded user instruction")
    _validate_task(root, config)
    _validate_denied_fields(root, config)
    _validate_conditions(config)
    if not isinstance(config.get("prompts"), dict) or set(config["prompts"]) != {"system", "user"}:
        raise TypeError("prompts must contain exactly system and user")
    if not isinstance(config.get("response_schema"), dict):
        raise TypeError("response schema must be a mapping")
    vocabulary = config["response_schema"].get("properties", {}).get("decision", {}).get("enum")
    if vocabulary != list(DECISION_VOCABULARY):
        raise ValueError("response schema decision vocabulary changed")
    _validate_model_lanes(root, config)
    claude = config.get("claude_lane")
    if not isinstance(claude, dict) or claude.get("admission") != "EXCLUDED_FROM_ONE_PAIR":
        raise ValueError("Claude exclusion record changed")


def load_cells(root: Path, config: dict[str, Any]) -> list[Cell]:
    """Build the four executions deterministically from the pair file."""
    pair_file = _safe_path(root, str(config["task"]["pair_file"]), Path("data/v2/generated"))
    wanted = set(config["task"]["pairs"])
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for line in pair_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("pair_id") in wanted:
            rows[(str(row["pair_id"]), str(row["variant"]))] = row
    cells: list[Cell] = []
    for condition in config["conditions"]:
        name = condition["name"]
        transmit = condition["transmit"]
        for pair_id in config["task"]["pairs"]:
            for variant in ("A", "B"):
                row = rows.get((pair_id, variant))
                if row is None:
                    raise ValueError(f"pair row missing: {pair_id} {variant}")
                approved = tuple(sorted(row["approved_fields"]))
                dataset_prohibited = tuple(sorted(row["prohibited_internal_fields"]))
                if transmit == ALL_RECORD_FIELDS:
                    selected = tuple(sorted(row["fields"].keys()))
                    prohibited = dataset_prohibited
                else:
                    selected = approved
                    prohibited = ()
                classify_projection(list(selected), list(approved), list(prohibited))
                records = tuple(
                    {field: row["fields"][field] for field in selected}
                    for _ in (0,)
                )
                approved_only = {
                    field: row["fields"][field] for field in approved
                }
                cells.append(
                    Cell(
                        condition=name,
                        variant=variant,
                        pair_id=pair_id,
                        selected_fields=selected,
                        approved_fields=approved,
                        prohibited_fields=prohibited,
                        dataset_prohibited_fields=dataset_prohibited,
                        records=records,
                        ground_truth=hmda_review_routing_ground_truth(approved_only),
                    )
                )
    if [cell.condition for cell in cells] != ["B0", "B0", "P3", "P3"] or [
        cell.variant for cell in cells
    ] != ["A", "B", "A", "B"]:
        raise ValueError("one-pair execution order is not B0-A, B0-B, P3-A, P3-B")
    return cells


def pair_release_policy(config: dict[str, Any]) -> dict[str, Any]:
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
        "policyRuleId": "finboundbench-v3-one-pair-validation-release",
        "requiredValidators": required,
        "jsonSchema": {"schema": config["response_schema"]},
        "requiredFields": {"paths": ["/decision", "/score", "/reason"]},
        "decisionVocabulary": {
            "path": "/decision",
            "permittedValues": list(DECISION_VOCABULARY),
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


def build_pair_bridge_payload(
    config: dict[str, Any], model: dict[str, Any], cell: Cell
) -> dict[str, Any]:
    records = [dict(record) for record in cell.records]
    material = {
        "validationId": config["validation_id"],
        "model": model["expected_model_id"],
        "route": model["expected_upstream_route"],
        "condition": cell.condition,
        "variant": cell.variant,
        "pairId": cell.pair_id,
        "selectedFields": list(cell.selected_fields),
        "approvedFields": list(cell.approved_fields),
        "prohibitedFields": list(cell.prohibited_fields),
        "recordsHash": sha256_json(records),
        "promptsHash": sha256_json(config["prompts"]),
        "responseSchemaHash": sha256_json(config["response_schema"]),
        "releasePolicyHash": sha256_json(pair_release_policy(config)),
        "seed": config["seed"],
    }
    return {
        "contractHash": sha256_json(material),
        "manifestRelativePath": model["manifest_path"],
        "workloadImageDigest": config["workload_image_digest"],
        "seed": config["seed"],
        "outputTokenLimit": config["output_token_limit"],
        "timeoutMs": config["timeout_ms"],
        "selectedFields": list(cell.selected_fields),
        "records": records,
        "prompts": config["prompts"],
        "responseSchema": config["response_schema"],
        "nativeReleasePolicy": pair_release_policy(config),
        "projectionClassification": {
            "approvedFields": list(cell.approved_fields),
            "prohibitedFields": list(cell.prohibited_fields),
        },
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


def _model_manifest_artifacts(root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _artifact(root, Path(model["manifest_path"]), "research")
        for model in config["models"]
    ]


def build_pair_validation_freeze(
    research_root: Path,
    platform_root: Path,
    *,
    research_commit: str,
    platform_commit: str,
) -> dict[str, Any]:
    config = _read_config(research_root)
    validate_pair_validation_config(research_root, config)
    load_cells(research_root, config)
    artifacts = [
        *(_artifact(research_root, path, "research") for path in RESEARCH_ARTIFACTS),
        *_model_manifest_artifacts(research_root, config),
        *(_artifact(platform_root, path, "platform") for path in PLATFORM_ARTIFACTS),
    ]
    core = {
        "schemaVersion": "finboundbench.openrouter-pair-validation-freeze.v3",
        "validationId": config["validation_id"],
        "scope": config["scope"],
        "status": "FROZEN_ONE_PAIR_VALIDATION_ONLY",
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


def verify_pair_validation_freeze(
    research_root: Path, platform_root: Path
) -> dict[str, Any]:
    config = _read_config(research_root)
    validate_pair_validation_config(research_root, config)
    load_cells(research_root, config)
    path = research_root / config["freeze_manifest_path"]
    value = json.loads(path.read_text(encoding="utf-8"))
    claimed_hash = value.pop("freezeManifestHash", None)
    if not isinstance(claimed_hash, str) or sha256_json(value) != claimed_hash:
        raise ValueError("one-pair validation freeze self-hash mismatch")
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


def _node_major() -> int:
    completed = subprocess.run(
        ["node", "--version"], capture_output=True, text=True, check=False
    )
    match = re.match(r"^v(\d+)\.", completed.stdout.strip())
    if not match:
        raise RuntimeError("node --version produced no usable version")
    return int(match.group(1))


def run_pair_validation(research_root: Path, platform_root: Path) -> dict[str, Any]:
    if _node_major() < NODE_MIN_MAJOR:
        raise RuntimeError(f"NODE_22_REQUIRED (found node v{_node_major()})")
    freeze = verify_pair_validation_freeze(research_root, platform_root)
    config = _read_config(research_root)
    raw_path = research_root / config["raw_events_path"]
    manifest_path = research_root / config["run_manifest_path"]
    if raw_path.exists() or manifest_path.exists():
        raise FileExistsError("one-pair validation results already exist; append-only run")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path = research_root / config["budget"]["ledger_path"]
    if ledger_path.exists() and read_jsonl(ledger_path):
        raise FileExistsError("one-pair ledger already has records; refusing to mix phases")
    budget = config["budget"]
    cells = load_cells(research_root, config)
    model = config["models"][0]
    previous = "0" * 64
    attempts = 0
    admitted = 0
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    environment["FINBOUNDBENCH_ROOT"] = str(research_root)
    for sequence, cell in enumerate(cells, start=1):
        attempts += 1
        payload = build_pair_bridge_payload(config, model, cell)
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
        outcome: dict[str, Any]
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
            decision = None
            if released:
                admitted += 1
                parsed = json.loads(result["quarantinedOutput"])
                decision = parsed.get("decision")
            outcome = {
                "status": "RELEASED" if released else "RELEASE_DENIED",
                "result": result,
                "decision": decision,
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
                "decision": None,
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
                "schemaVersion": "finboundbench.openrouter-pair-validation-event.v3",
                "validationLabel": VALIDATION_LABEL,
                "sequence": sequence,
                "condition": cell.condition,
                "variant": cell.variant,
                "pairId": cell.pair_id,
                "laneId": model["lane_id"],
                "expectedModelId": model["expected_model_id"],
                "expectedUpstreamRoute": model["expected_upstream_route"],
                "expectedManifestHash": model["expected_manifest_hash"],
                "contractHash": payload["contractHash"],
                "advertisedSelectedFields": list(cell.selected_fields),
                "advertisedApprovedFields": list(cell.approved_fields),
                "advertisedProhibitedFields": list(cell.prohibited_fields),
                "datasetProhibitedFields": list(cell.dataset_prohibited_fields),
                "groundTruth": cell.ground_truth,
                "projectionHash": sha256_json([dict(r) for r in cell.records]),
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
        "schemaVersion": "finboundbench.openrouter-pair-validation-run.v3",
        "validationLabel": VALIDATION_LABEL,
        "validationId": config["validation_id"],
        "status": (
            "PASSED_ONE_PAIR_VALIDATION" if admitted == attempts else "COMPLETED_WITH_RETAINED_FAILURES"
        ),
        "freezeManifestHash": freeze["freezeManifestHash"],
        "repositoryBindings": freeze["repositoryBindings"],
        "attempts": attempts,
        "released": admitted,
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
    return verify_pair_validation(research_root, platform_root)


def _event_evidence(event: dict[str, Any]) -> dict[str, Any]:
    result = event.get("result")
    if not isinstance(result, dict):
        return {}
    evidence = result.get("evidence")
    if not isinstance(evidence, dict):
        return {}
    return evidence


def verify_pair_validation(research_root: Path, platform_root: Path) -> dict[str, Any]:
    freeze = verify_pair_validation_freeze(research_root, platform_root)
    config = _read_config(research_root)
    manifest_path = research_root / config["run_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed = manifest.pop("manifestHash", None)
    if not isinstance(claimed, str) or sha256_json(manifest) != claimed:
        raise ValueError("one-pair validation run manifest self-hash mismatch")
    manifest["manifestHash"] = claimed
    if manifest["freezeManifestHash"] != freeze["freezeManifestHash"]:
        raise ValueError("one-pair validation run is not bound to the active freeze")
    raw_path = research_root / manifest["rawArtifact"]["path"]
    if sha256_file(raw_path) != manifest["rawArtifact"]["sha256"]:
        raise ValueError("one-pair validation raw artifact hash mismatch")
    events = read_jsonl(raw_path)
    if len(events) != manifest["attempts"] or len(events) != 4:
        raise ValueError("one-pair validation event count mismatch")
    ledger_path = research_root / config["budget"]["ledger_path"]
    ledger_rows = read_jsonl(ledger_path)
    if len(ledger_rows) != manifest["budget"]["ledgerRecordCount"] or sha256_json(
        ledger_rows
    ) != manifest["budget"]["ledgerHash"]:
        raise ValueError("one-pair validation budget ledger changed after the run")
    if committed_budget_eur(ledger_rows) != manifest["budget"]["committedEur"]:
        raise ValueError("one-pair validation committed budget mismatch")
    if committed_budget_eur(ledger_rows) > float(config["budget"]["absolute_authorized_eur"]):
        raise ValueError("one-pair validation exceeded the absolute authorization")
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
        raise ValueError("one-pair reservations are not completely settled")
    cells = load_cells(research_root, config)
    previous = "0" * 64
    released = 0
    by_condition: dict[str, dict[str, dict[str, Any]]] = {"B0": {}, "P3": {}}
    for sequence, (event, cell) in enumerate(zip(events, cells, strict=True), start=1):
        event_hash = event.pop("eventHash", None)
        if event.get("previousEventHash") != previous or sha256_json(event) != event_hash:
            raise ValueError("one-pair validation event chain mismatch")
        event["eventHash"] = event_hash
        previous = event_hash
        if (
            event["sequence"] != sequence
            or event["condition"] != cell.condition
            or event["variant"] != cell.variant
            or event["pairId"] != cell.pair_id
        ):
            raise ValueError("one-pair execution ordering mismatch")
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
            raise ValueError("one-pair safety invariant failed")
        if (
            event["advertisedSelectedFields"] != list(cell.selected_fields)
            or event["advertisedApprovedFields"] != list(cell.approved_fields)
            or event["advertisedProhibitedFields"] != list(cell.prohibited_fields)
            or event["datasetProhibitedFields"] != list(cell.dataset_prohibited_fields)
            or event["groundTruth"] != cell.ground_truth
        ):
            raise ValueError("one-pair advertised partition or truth mismatch")
        if event["condition"] == "B0" and event["advertisedProhibitedFields"] != event[
            "datasetProhibitedFields"
        ]:
            raise ValueError("B0 must transmit every dataset-prohibited field")
        if event["condition"] == "P3" and event["advertisedProhibitedFields"]:
            raise ValueError("P3 must transmit no prohibited field")
        if event["status"] == "RELEASED":
            result = event["result"]
            evidence = result["evidence"]
            release = result["nativeRelease"]
            if evidence["destinationHost"] != "openrouter.ai":
                raise ValueError("observed OpenRouter destination mismatch")
            if evidence["processingClassification"] != "REMOTE_PROVIDER_PROCESSING":
                raise ValueError("processing classification is not remote")
            if evidence["contractHash"] != event["contractHash"]:
                raise ValueError("one-pair evidence contract mismatch")
            if evidence["transmittedFields"] != list(cell.selected_fields):
                raise ValueError("one-pair evidence projection mismatch")
            for field in ("transmittedApprovedFields", "transmittedProhibitedFields"):
                if field not in evidence:
                    raise ValueError("projection classification was not forwarded to evidence")
            if evidence["transmittedApprovedFields"] != list(cell.approved_fields):
                raise ValueError("evidence approved partition mismatch")
            if evidence["transmittedProhibitedFields"] != list(cell.prohibited_fields):
                raise ValueError("evidence prohibited partition mismatch")
            expected_approved_hash = projection_payload_hash(
                [dict(r) for r in cell.records], list(cell.approved_fields)
            )
            if evidence["approvedPayloadHash"] != expected_approved_hash:
                raise ValueError("platform approved hash disagrees with research hash")
            if not release["allowed"] or any(
                item["decision"] == "DENY" for item in release["events"]
            ):
                raise ValueError("released execution did not pass native release")
            if event["decision"] not in DECISION_VOCABULARY:
                raise ValueError("released execution returned an invalid decision")
            if event["decision"] != cell.ground_truth:
                raise ValueError(
                    f"task utility failure: decision {event['decision']} != truth {cell.ground_truth}"
                )
            by_condition[cell.condition][cell.variant] = evidence
            released += 1
    b0 = by_condition["B0"]
    p3 = by_condition["P3"]
    if set(b0) != {"A", "B"} or set(p3) != {"A", "B"}:
        raise ValueError("one-pair validation did not release all four executions")
    if b0["A"]["approvedPayloadHash"] != b0["B"]["approvedPayloadHash"]:
        raise ValueError("B0 variants transmitted different approved projections")
    if p3["A"]["approvedPayloadHash"] != p3["B"]["approvedPayloadHash"]:
        raise ValueError("P3 variants transmitted different approved projections")
    if b0["A"]["prohibitedPayloadHash"] == b0["B"]["prohibitedPayloadHash"]:
        raise ValueError("B0 variants did not differ in prohibited fields")
    if b0["A"]["payloadHash"] == b0["B"]["payloadHash"]:
        raise ValueError("B0 full request bodies must differ between variants")
    if p3["A"]["payloadHash"] != p3["B"]["payloadHash"]:
        raise ValueError("P3 full request bodies must be identical between variants")
    if previous != manifest["finalEventHash"] or released != manifest["released"]:
        raise ValueError("one-pair validation summary mismatch")
    text = raw_path.read_text(encoding="utf-8").lower()
    if any(marker.lower() in text for marker in FORBIDDEN_SECRET_MARKERS):
        raise ValueError("provider secret marker found in one-pair validation evidence")
    return manifest


def current_repository_bindings(research_root: Path, platform_root: Path) -> dict[str, str]:
    return {"researchCommit": git_commit(research_root), "platformCommit": git_commit(platform_root)}