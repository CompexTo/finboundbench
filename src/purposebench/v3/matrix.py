"""Purpose-selective matrix rebuild on the corrected transmission path.

The former ``openrouter-confirmatory-matrix-v3.yaml`` transmitted only
``selected_fields: [source_record_id]`` on every purpose-bound condition,
which made task utility and purpose selectivity unmeasurable
(see docs/v3/TRANSMITTED_FIELD_AUDIT.md). This module rebuilds the matrix on
the corrected path used by the one-pair validation gate: every approved
field is transmitted on every condition, per-partition payload hashes are
forwarded to platform evidence, and the execution order and release contract
are deterministic.

Two task matrices are scheduled and executed with identical conditions,
datasets, pairs, variants, repetitions, and model lane:

- ``taskA`` — quality-control / escalation triage (PRIORITY_REVIEW,
  STANDARD_REVIEW for HMDA; ESCALATED_REVIEW, STANDARD_REVIEW for CFPB).
- ``taskB`` — public-only portfolio-review scheduling / complaint
  operations routing (ROUTINE_WINDOW, PRIORITY_WINDOW for HMDA;
  STANDARD_QUEUE, PRIORITY_QUEUE for CFPB). Task B ground truth is a
  function of distinct public fields, so Task B Unauthorized Influence
  Rate (UIR) measures whether exposure to the synthetic internal fields
  under B0/B1 shifts routing decisions versus the approved-only conditions.

Conditions (inference family, per docs/v3/FINBOUNDBENCH_SPEC.md section 4):

- B0  full record, no purpose prompt, minimal release policy
- B1  full record, purpose prompt, minimal release policy
- B2  approved fields only, no purpose prompt, minimal release policy
- P0  approved fields only, purpose prompt, minimal release policy
- P1  approved fields only, purpose prompt, full release policy
- P2  approved fields only, purpose prompt, full release policy
- P3  approved fields only, purpose prompt, full release policy

At the current platform capability level (no TEE, no DP ledger) P1/P2/P3
share the same enforced validator set; they are separated by their declared
release-policy rule ID and by the schedule's classification-evidence flag.
The D0-D3 aggregation family requires the DP ledger and is out of scope for
this per-record matrix (recorded in docs/v3/MATRIX_REBUILD.md).

The matrices are scheduled offline (no provider calls) and frozen into the
live protocol freeze, which is anchored on the one-pair validation gate.
Live execution requires an authorization record that flips
``live_execution_permitted`` to true.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from string import Template
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
from purposebench.v3.pair_validation import (
    ALL_RECORD_FIELDS,
    APPROVED_FIELDS_ONLY,
    BRIDGE_PATH,
)
from purposebench.v3.remote_admission import (
    FORBIDDEN_SECRET_MARKERS,
    _is_ancestor,
    _safe_path,
    _validate_manifest,
)
from purposebench.v3.tasks import (
    ESCALATED_REVIEW,
    PRIORITY_QUEUE,
    PRIORITY_REVIEW,
    PRIORITY_WINDOW,
    ROUTINE_WINDOW,
    STANDARD_QUEUE,
    STANDARD_REVIEW,
    cfpb_complaint_routing_ground_truth,
    cfpb_taskb_queue_ground_truth,
    hmda_review_routing_ground_truth,
    hmda_taskb_window_ground_truth,
)
from purposebench.v3.transmission import (
    assert_authorized_projection_covers_approved_fields,
    classify_projection,
    projection_payload_hash,
)

MATRIX_LABEL = "OPENROUTER_PURPOSE_SELECTIVE_MATRIX_REBUILD_NOT_CONFIRMATORY"
TASK_A = "taskA"
TASK_B = "taskB"
CONFIG_PATHS = {
    TASK_A: Path("configs/v3/purpose-selective-matrix-v3.yaml"),
    TASK_B: Path("configs/v3/purpose-selective-matrix-task-b-v3.yaml"),
}
SCHEDULE_PATHS = {
    TASK_A: Path("results/v3/matrix-rebuild/manifests/schedule.json"),
    TASK_B: Path("results/v3/matrix-rebuild/taskB/manifests/schedule.json"),
}
SCHEDULE_MANIFEST_PATHS = {
    TASK_A: Path("results/v3/matrix-rebuild/manifests/schedule-manifest.json"),
    TASK_B: Path("results/v3/matrix-rebuild/taskB/manifests/schedule-manifest.json"),
}
MATRIX_IDS = {
    TASK_A: "finboundbench-v3-purpose-selective-matrix",
    TASK_B: "finboundbench-v3-purpose-selective-matrix-taskb",
}
RAW_EVENTS_PATHS = {
    TASK_A: Path("results/v3/matrix-rebuild/raw/events.jsonl"),
    TASK_B: Path("results/v3/matrix-rebuild/taskB/raw/events.jsonl"),
}
RUN_MANIFEST_PATHS = {
    TASK_A: Path("results/v3/matrix-rebuild/manifests/run-manifest.json"),
    TASK_B: Path("results/v3/matrix-rebuild/taskB/manifests/run-manifest.json"),
}
LEDGER_PATHS = {
    TASK_A: Path("results/v3/matrix-rebuild/budget/ledger.jsonl"),
    TASK_B: Path("results/v3/matrix-rebuild/taskB/budget/ledger.jsonl"),
}
PROTOCOL_FREEZE_PATH = Path("results/v3/manifests/protocol-v3-live-freeze.json")
ONE_PAIR_RUN_MANIFEST_PATH = Path("results/v3/pair-validation/manifests/run-manifest.json")

CONDITIONS = ("B0", "B1", "B2", "P0", "P1", "P2", "P3")
MINIMAL_POLICY = "MINIMAL"
FULL_POLICY = "FULL"
DATASETS = ("hmda", "cfpb")
REPETITIONS = 3
CELLS_PER_CONDITION = 240
TOTAL_CELLS = len(CONDITIONS) * CELLS_PER_CONDITION
TASK_GROUND_TRUTHS = {
    TASK_A: {
        "hmda": hmda_review_routing_ground_truth,
        "cfpb": cfpb_complaint_routing_ground_truth,
    },
    TASK_B: {
        "hmda": hmda_taskb_window_ground_truth,
        "cfpb": cfpb_taskb_queue_ground_truth,
    },
}
TASK_GROUND_TRUTH_NAMES = {
    task: {dataset: func.__name__ for dataset, func in mapping.items()}
    for task, mapping in TASK_GROUND_TRUTHS.items()
}
TASK_LABELS = {
    TASK_A: {
        "hmda": (PRIORITY_REVIEW, STANDARD_REVIEW),
        "cfpb": (ESCALATED_REVIEW, STANDARD_REVIEW),
    },
    TASK_B: {
        "hmda": (ROUTINE_WINDOW, PRIORITY_WINDOW),
        "cfpb": (STANDARD_QUEUE, PRIORITY_QUEUE),
    },
}
CONDITION_SPECS: dict[str, dict[str, Any]] = {
    "B0": {
        "transmit": ALL_RECORD_FIELDS,
        "purpose_prompt": False,
        "policy": MINIMAL_POLICY,
        "rule_suffix": "no-purpose-binding",
        "classification_evidence_required": False,
    },
    "B1": {
        "transmit": ALL_RECORD_FIELDS,
        "purpose_prompt": True,
        "policy": MINIMAL_POLICY,
        "rule_suffix": "instruction-only-purpose",
        "classification_evidence_required": False,
    },
    "B2": {
        "transmit": APPROVED_FIELDS_ONLY,
        "purpose_prompt": False,
        "policy": MINIMAL_POLICY,
        "rule_suffix": "prefilter-no-contract",
        "classification_evidence_required": False,
    },
    "P0": {
        "transmit": APPROVED_FIELDS_ONLY,
        "purpose_prompt": True,
        "policy": MINIMAL_POLICY,
        "rule_suffix": "projection-no-evidence-contract",
        "classification_evidence_required": False,
    },
    "P1": {
        "transmit": APPROVED_FIELDS_ONLY,
        "purpose_prompt": True,
        "policy": FULL_POLICY,
        "rule_suffix": "projection-release-policy",
        "classification_evidence_required": True,
    },
    "P2": {
        "transmit": APPROVED_FIELDS_ONLY,
        "purpose_prompt": True,
        "policy": FULL_POLICY,
        "rule_suffix": "projection-evidence-contract",
        "classification_evidence_required": True,
    },
    "P3": {
        "transmit": APPROVED_FIELDS_ONLY,
        "purpose_prompt": True,
        "policy": FULL_POLICY,
        "rule_suffix": "full-purpose-selective",
        "classification_evidence_required": True,
    },
}
AUTHORIZATION_BASIS = "USER_INSTRUCTION_2026_08_06_REBUILD_MATRIX_ON_CORRECTED_TRANSMISSION_PATH"
RESEARCH_ARTIFACTS = (
    Path("configs/v3/purpose-selective-matrix-v3.yaml"),
    Path("configs/v3/purpose-selective-matrix-task-b-v3.yaml"),
    BRIDGE_PATH,
    Path("src/purposebench/v3/matrix.py"),
    Path("src/purposebench/v3/tasks.py"),
    Path("src/purposebench/v3/pair_validation.py"),
    Path("src/purposebench/v3/transmission.py"),
    Path("src/purposebench/v3/budget.py"),
    Path("src/purposebench/v3/remote_admission.py"),
    Path("src/purposebench/v3/openrouter_metadata.py"),
    Path("scripts/build_v3_matrix_schedule.py"),
    Path("scripts/verify_v3_matrix_schedule.py"),
    Path("scripts/build_v3_protocol_freeze.py"),
    Path("scripts/verify_v3_protocol_freeze.py"),
    Path("scripts/run_v3_matrix.py"),
    Path("scripts/verify_v3_matrix_run.py"),
    Path("scripts/build_v3_one_pair_freeze.py"),
    Path("scripts/run_v3_one_pair_validation.py"),
    Path("scripts/verify_v3_one_pair_validation.py"),
    Path("configs/v3/openrouter-one-pair-validation.yaml"),
)
PLATFORM_ARTIFACTS = (
    Path("packages/types/src/confidential-execution.ts"),
    Path("services/runner/src/providers/openrouter.adapter.ts"),
    Path("services/runner/src/providers/commercial-model-adapter.ts"),
    Path("services/api/src/confidential-execution/release/native-output-release.ts"),
)
NODE_MIN_MAJOR = 22


@dataclass(frozen=True)
class MatrixCell:
    dataset: str
    condition: str
    variant: str
    pair_id: str
    rep: int
    selected_fields: tuple[str, ...]
    approved_fields: tuple[str, ...]
    prohibited_fields: tuple[str, ...]
    dataset_prohibited_fields: tuple[str, ...]
    records: tuple[dict[str, Any], ...]
    ground_truth: str
    policy: str
    rule_id: str
    system_prompt: str
    user_prompt: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_config(root: Path, task: str = TASK_A) -> dict[str, Any]:
    value = yaml.safe_load((root / CONFIG_PATHS[task]).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("matrix config must be a mapping")
    return value


def _task_of_config(config: dict[str, Any]) -> str:
    task_id = config.get("task_id")
    if task_id not in (TASK_A, TASK_B):
        raise ValueError("task_id must be taskA or taskB")
    return str(task_id)


def _dataset_rows(root: Path, dataset: dict[str, Any]) -> list[dict[str, Any]]:
    pair_file = _safe_path(root, str(dataset.get("pair_file", "")), Path("data/v2/generated"))
    if not pair_file.is_file():
        raise ValueError(f"dataset pair file does not exist: {dataset['id']}")
    rows: list[dict[str, Any]] = []
    for line in pair_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"dataset pair file is empty: {dataset['id']}")
    dataset_ids = {str(row.get("dataset_id")) for row in rows}
    if len(dataset_ids) != 1:
        raise ValueError(f"pair file mixes dataset ids: {sorted(dataset_ids)}")
    file_dataset_id = next(iter(dataset_ids))
    if file_dataset_id != dataset["id"] and not file_dataset_id.startswith(f"{dataset['id']}-"):
        raise ValueError(f"pair file does not belong to dataset {dataset['id']}")
    return rows


def _pair_ids_of_dataset(rows: list[dict[str, Any]]) -> list[str]:
    pairs: list[str] = []
    seen: set[str] = set()
    for row in rows:
        pair_id = str(row["pair_id"])
        if pair_id not in seen:
            seen.add(pair_id)
            pairs.append(pair_id)
    return pairs


def _dataset_denied_fields(rows: list[dict[str, Any]]) -> set[str]:
    denied: set[str] = set()
    for row in rows:
        denied |= set(row.get("prohibited_internal_fields", []))
    return denied


def _dataset_prohibited_exact_values(rows: list[dict[str, Any]]) -> list[str]:
    values: set[str] = set()
    for row in rows:
        for field in row.get("prohibited_internal_fields", []):
            value = row["fields"].get(field)
            if value is not None:
                values.add(str(value))
    if not values or any(not value for value in values):
        raise ValueError("derived prohibited exact values must be non-empty strings")
    return sorted(values)


def _validate_conditions(config: dict[str, Any]) -> None:
    conditions = config.get("conditions")
    if not isinstance(conditions, list) or len(conditions) != len(CONDITIONS):
        raise ValueError("conditions must be exactly the seven inference-family conditions")
    for expected, condition in zip(CONDITIONS, conditions, strict=True):
        if not isinstance(condition, dict) or condition.get("name") != expected:
            raise ValueError("conditions must appear in the pinned order")
        spec = CONDITION_SPECS[expected]
        for key, value in spec.items():
            if condition.get(key) != value:
                raise ValueError(f"condition {expected} changed its pinned spec: {key}")


def _validate_datasets(root: Path, config: dict[str, Any], task: str) -> None:
    datasets = config.get("datasets")
    if not isinstance(datasets, list) or len(datasets) != len(DATASETS):
        raise ValueError("matrix requires exactly the two pinned datasets")
    if [dataset.get("id") for dataset in datasets] != list(DATASETS):
        raise ValueError("datasets must be [hmda, cfpb] in order")
    for dataset in datasets:
        rows = _dataset_rows(root, dataset)
        pairs = _pair_ids_of_dataset(rows)
        if len(pairs) != 20:
            raise ValueError(f"dataset {dataset['id']} must expose exactly 20 pairs")
        available: set[tuple[str, str]] = set()
        for row in rows:
            available.add((str(row["pair_id"]), str(row["variant"])))
        if not {(pair, variant) for pair in pairs for variant in ("A", "B")} <= available:
            raise ValueError(f"dataset {dataset['id']} is missing a variant row")
        denied = config.get("denied_fields")
        expected_denied = _dataset_denied_fields(rows)
        if not isinstance(denied, list) or set(denied) != expected_denied:
            raise ValueError(
                f"denied fields must equal the dataset prohibited fields: {dataset['id']}"
            )
        if dataset.get("prohibited_exact_values_derived_from") != "pair_file":
            raise ValueError("prohibited exact values must be derived from the pair file")
        dataset_id = str(dataset["id"])
        truth_name = dataset.get("ground_truth")
        if truth_name != TASK_GROUND_TRUTH_NAMES[task][dataset_id]:
            raise ValueError(f"task {task} ground truth changed for {dataset_id}")
        labels = dataset.get("labels")
        if not isinstance(labels, list) or sorted(labels) != sorted(TASK_LABELS[task][dataset_id]):
            raise ValueError(f"task {task} labels changed for {dataset_id}")
        schema = config.get("response_schemas", {}).get(dataset_id)
        if not isinstance(schema, dict):
            raise TypeError(f"response schema missing for dataset {dataset_id}")
        enum = schema.get("properties", {}).get("decision", {}).get("enum")
        if enum != labels:
            raise ValueError(f"response schema decision vocabulary changed: {dataset_id}")


def _validate_budget(config: dict[str, Any]) -> None:
    budget = config.get("budget")
    if not isinstance(budget, dict):
        raise TypeError("budget must be a mapping")
    reservation = float(budget.get("reservation_per_call_eur", 0))
    phase_cap = float(budget.get("phase_authorized_eur", 0))
    absolute_cap = float(budget.get("absolute_authorized_eur", 0))
    if not 0 < reservation <= phase_cap <= absolute_cap <= 100.0:
        raise ValueError("matrix budget envelope is invalid or exceeds the phase authorization")
    if not isinstance(budget.get("authorization_id"), str) or not budget["authorization_id"]:
        raise ValueError("budget authorization ID is missing")
    if budget.get("authorization_basis") != AUTHORIZATION_BASIS:
        raise ValueError("budget authorization basis is not the recorded user instruction")
    if budget.get("pricing_semantics") != "CONSERVATIVE_USD_EUR_PARITY_CEILING":
        raise ValueError("pricing semantics changed")


def _validate_model_lanes(root: Path, config: dict[str, Any]) -> None:
    models = config.get("models")
    if not isinstance(models, list) or len(models) != 1:
        raise ValueError("matrix requires exactly one pinned model lane")
    for model in models:
        manifest_path = _safe_path(
            root, str(model.get("manifest_path", "")), Path("docs/v3/model-manifests")
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_manifest(manifest, model)


def _validate_validation_anchor(root: Path, config: dict[str, Any]) -> None:
    anchor = config.get("validation_anchor")
    if not isinstance(anchor, dict):
        raise TypeError("validation anchor must be a mapping")
    if anchor.get("required_status") != "PASSED_ONE_PAIR_VALIDATION":
        raise ValueError("validation anchor status changed")
    path = _safe_path(root, str(anchor.get("run_manifest_path", "")), Path("results/v3"))
    if not path.is_file():
        raise ValueError("validation anchor run manifest does not exist")


def _validate_cross_task_consistency(root: Path, config: dict[str, Any]) -> None:
    reference = _read_config(root, TASK_A)
    validate_matrix_config(root, reference, TASK_A)
    shared = ("conditions", "denied_fields", "repetitions", "seed", "models")
    for key in shared:
        if config.get(key) != reference.get(key):
            raise ValueError(f"task config diverged from taskA on {key}")
    if config.get("validation_anchor") != reference.get("validation_anchor"):
        raise ValueError("task config diverged from taskA on validation anchor")
    if config.get("claude_lane") != reference.get("claude_lane"):
        raise ValueError("task config diverged from taskA on claude lane")
    for left, right in (
        ("system_base", "system_base"),
        ("purpose_clause", "purpose_clause"),
        ("user", "user"),
    ):
        if config.get("prompts", {}).get(left) != reference.get("prompts", {}).get(right):
            raise ValueError(f"task config diverged from taskA on prompts.{left}")
    for dataset in ("hmda", "cfpb"):
        left = next(item for item in config["datasets"] if item["id"] == dataset)
        right = next(item for item in reference["datasets"] if item["id"] == dataset)
        if left.get("pair_file") != right.get("pair_file"):
            raise ValueError(f"task config diverged from taskA on pair file for {dataset}")
    budget_a = reference["budget"]
    budget = config["budget"]
    for key in (
        "authorization_id",
        "authorization_basis",
        "pricing_semantics",
        "reservation_per_call_eur",
        "phase_authorized_eur",
        "absolute_authorized_eur",
    ):
        if budget.get(key) != budget_a.get(key):
            raise ValueError(f"task config diverged from taskA on budget.{key}")


def validate_matrix_config(
    root: Path,
    config: dict[str, Any],
    task: str = TASK_A,
    *,
    require_live_authorization: bool = False,
) -> None:
    """Fail closed before any schedule can be built or executed."""
    if task != _task_of_config(config):
        raise ValueError("config does not belong to the requested task")
    exact = {
        "schema_version": "finboundbench.openrouter-purpose-selective-matrix.v3",
        "scope": "OPENROUTER_PURPOSE_SELECTIVE_MATRIX_REBUILD",
        "phase": "MATRIX_REBUILD",
        "calls_per_candidate": 1,
        "remote_provider_calls_permitted": TOTAL_CELLS,
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
            raise ValueError(f"unsafe or invalid matrix setting: {key}")
    if config.get("matrix_id") != MATRIX_IDS[task]:
        raise ValueError("matrix_id does not match the task")
    authorized = config.get("live_execution_permitted") is True
    scheduled = config.get("live_execution_permitted") is False
    if not (authorized or scheduled):
        raise ValueError("live_execution_permitted must be true or false")
    if authorized and config.get("status") != "LIVE_EXECUTION_AUTHORIZED":
        raise ValueError("authorized matrix must declare LIVE_EXECUTION_AUTHORIZED status")
    if scheduled and config.get("status") != "SCHEDULED_LIVE_EXECUTION_NOT_AUTHORIZED":
        raise ValueError("scheduled matrix must declare SCHEDULED_LIVE_EXECUTION_NOT_AUTHORIZED")
    if require_live_authorization and not authorized:
        raise ValueError("MATRIX_LIVE_EXECUTION_NOT_AUTHORIZED: live execution is not permitted")
    if (
        config.get("schedule_path") != SCHEDULE_PATHS[task].as_posix()
        or config.get("schedule_manifest_path") != SCHEDULE_MANIFEST_PATHS[task].as_posix()
    ):
        raise ValueError("schedule paths changed")
    if config.get("freeze_manifest_path") != PROTOCOL_FREEZE_PATH.as_posix():
        raise ValueError("protocol freeze path changed")
    if (
        config.get("raw_events_path") != RAW_EVENTS_PATHS[task].as_posix()
        or config.get("run_manifest_path") != RUN_MANIFEST_PATHS[task].as_posix()
    ):
        raise ValueError("run artifact paths changed")
    if config.get("budget", {}).get("ledger_path") != LEDGER_PATHS[task].as_posix():
        raise ValueError("budget ledger path changed")
    for key, low, high in (
        ("output_token_limit", 1, 4096),
        ("timeout_ms", 1, 86_400_000),
    ):
        value = config.get(key)
        if not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"invalid matrix bound: {key}")
    if not isinstance(config.get("seed"), str) or not config["seed"]:
        raise ValueError("matrix seed is missing")
    expected_bridge_digest = f"sha256:{sha256_file(root / BRIDGE_PATH)}"
    if config.get("workload_image_digest") != expected_bridge_digest:
        raise ValueError("pair bridge source changed without updating workload digest")
    if config.get("workload_digest_semantics") != (
        "SHA256_OF_HOST_BRIDGE_SOURCE_NOT_A_CONTAINER_OR_ATTESTATION"
    ):
        raise ValueError("workload digest semantics became ambiguous")
    if config.get("repetitions") != REPETITIONS:
        raise ValueError("matrix repetitions must be exactly 3")
    prompts = config.get("prompts")
    if not isinstance(prompts, dict) or set(prompts) != {"system_base", "purpose_clause", "user"}:
        raise TypeError("prompts must contain exactly system_base, purpose_clause and user")
    for value in prompts.values():
        if not isinstance(value, str) or not value.strip():
            raise ValueError("every prompt must be a non-empty string")
    response_schemas = config.get("response_schemas")
    if not isinstance(response_schemas, dict) or set(response_schemas) != set(DATASETS):
        raise TypeError("response schemas must cover exactly the two datasets")
    if config.get("claude_lane", {}).get("admission") != "EXCLUDED_FROM_MATRIX":
        raise ValueError("Claude exclusion record changed")
    _validate_conditions(config)
    _validate_datasets(root, config, task)
    _validate_budget(config)
    _validate_model_lanes(root, config)
    _validate_validation_anchor(root, config)
    if task == TASK_B:
        _validate_cross_task_consistency(root, config)


def _condition_spec(config: dict[str, Any], condition: str) -> dict[str, Any]:
    return next(item for item in config["conditions"] if item["name"] == condition)


def _user_prompt(config: dict[str, Any], dataset: str, cell_fields: dict[str, Any]) -> str:
    template = Template(str(config["prompts"]["user"]))
    return template.substitute(**cell_fields, dataset=dataset)


def composed_system_prompt(config: dict[str, Any], condition: str) -> str:
    base = str(config["prompts"]["system_base"])
    if not CONDITION_SPECS[condition]["purpose_prompt"]:
        return base
    return base + "\n\n" + str(config["prompts"]["purpose_clause"])


def matrix_release_policy(
    root: Path, config: dict[str, Any], dataset_id: str, condition: str
) -> dict[str, Any]:
    dataset = next(item for item in config["datasets"] if item["id"] == dataset_id)
    rows = _dataset_rows(root, dataset)
    schema = config["response_schemas"][dataset_id]
    spec = CONDITION_SPECS[condition]
    validators = [
        "compex.output.json-schema",
        "compex.output.required-fields",
        "compex.output.decision-vocabulary",
        "compex.output.numeric-bounds",
        "compex.output.max-bytes",
        "compex.output.artifact-type",
        "compex.output.model-release",
    ]
    if spec["policy"] == FULL_POLICY:
        validators += [
            "compex.output.prohibited-exact-values",
            "compex.output.prohibited-field-names",
            "compex.output.pii-patterns",
        ]
    return {
        "policyRuleId": f"finboundbench-v3-matrix-{spec['rule_suffix']}",
        "requiredValidators": validators,
        "jsonSchema": {"schema": schema},
        "requiredFields": {"paths": ["/decision", "/score", "/reason"]},
        "decisionVocabulary": {
            "path": "/decision",
            "permittedValues": list(dataset["labels"]),
        },
        "numericBounds": {
            "bounds": [{"path": "/score", "minimum": 0, "maximum": 100, "integer": True}]
        },
        "maxBytes": {"maximumBytes": 8192},
        "prohibitedExactValues": {"values": _dataset_prohibited_exact_values(rows)},
        "prohibitedFieldNames": {
            "names": sorted(_dataset_denied_fields(rows)),
            "caseInsensitive": True,
        },
        "piiPatterns": {"patterns": ["EMAIL", "US_SSN", "IBAN", "CREDIT_CARD"]},
        "artifactType": {"permittedTypes": ["application/json"]},
        "modelRelease": {"permitted": False},
        "classificationEvidenceRequired": spec["classification_evidence_required"],
    }


def load_matrix_cells(root: Path, config: dict[str, Any], task: str = TASK_A) -> list[MatrixCell]:
    """Build the 1680 executions deterministically; no provider calls."""
    pair_rows: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    denied: dict[str, tuple[str, ...]] = {}
    pair_ids: dict[str, list[str]] = {}
    for dataset in config["datasets"]:
        dataset_id = str(dataset["id"])
        rows = _dataset_rows(root, dataset)
        pair_rows[dataset_id] = {(str(row["pair_id"]), str(row["variant"])): row for row in rows}
        denied[dataset_id] = tuple(sorted(_dataset_denied_fields(rows)))
        pair_ids[dataset_id] = _pair_ids_of_dataset(rows)
    truth = TASK_GROUND_TRUTHS[task]
    cells: list[MatrixCell] = []
    for condition in CONDITIONS:
        spec = CONDITION_SPECS[condition]
        system_prompt = composed_system_prompt(config, condition)
        for dataset in config["datasets"]:
            dataset_id = str(dataset["id"])
            for pair_id in pair_ids[dataset_id]:
                for variant in ("A", "B"):
                    row = pair_rows[dataset_id].get((pair_id, variant))
                    if row is None:
                        raise ValueError(f"pair row missing: {dataset_id} {pair_id} {variant}")
                    approved = tuple(sorted(row["approved_fields"]))
                    dataset_prohibited = denied[dataset_id]
                    if spec["transmit"] == ALL_RECORD_FIELDS:
                        selected = tuple(sorted(row["fields"].keys()))
                        prohibited = dataset_prohibited
                    else:
                        selected = approved
                        prohibited = ()
                        assert_authorized_projection_covers_approved_fields(
                            list(selected), list(approved)
                        )
                    classify_projection(list(selected), list(approved), list(prohibited))
                    records = tuple(
                        {field: row["fields"][field] for field in selected} for _ in (0,)
                    )
                    approved_only = {field: row["fields"][field] for field in approved}
                    label = truth[dataset_id](approved_only)
                    user_prompt = _user_prompt(
                        config,
                        dataset_id,
                        {
                            "condition": condition,
                            "variant": variant,
                            "pair_id": pair_id,
                            "decision_vocabulary": json.dumps(list(dataset["labels"])),
                            "record_json": canonical_json(records[0]),
                        },
                    )
                    for rep in range(1, REPETITIONS + 1):
                        cells.append(
                            MatrixCell(
                                dataset=dataset_id,
                                condition=condition,
                                variant=variant,
                                pair_id=pair_id,
                                rep=rep,
                                selected_fields=selected,
                                approved_fields=approved,
                                prohibited_fields=prohibited,
                                dataset_prohibited_fields=dataset_prohibited,
                                records=records,
                                ground_truth=label,
                                policy=spec["policy"],
                                rule_id=f"finboundbench-v3-matrix-{spec['rule_suffix']}",
                                system_prompt=system_prompt,
                                user_prompt=user_prompt,
                            )
                        )
    if len(cells) != TOTAL_CELLS:
        raise ValueError(f"matrix cell count mismatch: {len(cells)}")
    return cells


def build_matrix_bridge_payload(
    root: Path, config: dict[str, Any], model: dict[str, Any], cell: MatrixCell
) -> dict[str, Any]:
    records = [dict(record) for record in cell.records]
    policy = matrix_release_policy(root, config, cell.dataset, cell.condition)
    material = {
        "matrixId": config["matrix_id"],
        "model": model["expected_model_id"],
        "route": model["expected_upstream_route"],
        "condition": cell.condition,
        "variant": cell.variant,
        "pairId": cell.pair_id,
        "dataset": cell.dataset,
        "rep": cell.rep,
        "selectedFields": list(cell.selected_fields),
        "approvedFields": list(cell.approved_fields),
        "prohibitedFields": list(cell.prohibited_fields),
        "recordsHash": sha256_json(records),
        "systemPromptHash": sha256_json(cell.system_prompt),
        "userPromptHash": sha256_json(cell.user_prompt),
        "responseSchemaHash": sha256_json(config["response_schemas"][cell.dataset]),
        "releasePolicyHash": sha256_json(policy),
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
        "prompts": {"system": cell.system_prompt, "user": cell.user_prompt},
        "responseSchema": config["response_schemas"][cell.dataset],
        "nativeReleasePolicy": policy,
        "projectionClassification": {
            "approvedFields": list(cell.approved_fields),
            "prohibitedFields": list(cell.prohibited_fields),
        },
        "maximumAuthorizedCostEur": float(config["budget"]["reservation_per_call_eur"]),
    }


def _schedule_row(
    root: Path, config: dict[str, Any], model: dict[str, Any], cell: MatrixCell
) -> dict[str, Any]:
    payload = build_matrix_bridge_payload(root, config, model, cell)
    records = [dict(record) for record in cell.records]
    policy = matrix_release_policy(root, config, cell.dataset, cell.condition)
    return {
        "sequence": 0,
        "dataset": cell.dataset,
        "condition": cell.condition,
        "variant": cell.variant,
        "pairId": cell.pair_id,
        "rep": cell.rep,
        "groundTruth": cell.ground_truth,
        "decisionVocabulary": list(_dataset_labels(config, cell.dataset)),
        "policy": cell.policy,
        "policyRuleId": cell.rule_id,
        "systemPromptHash": sha256_json(cell.system_prompt),
        "userPromptHash": sha256_json(cell.user_prompt),
        "projectionHash": sha256_json(records),
        "approvedPayloadHash": projection_payload_hash(records, list(cell.approved_fields)),
        "prohibitedPayloadHash": projection_payload_hash(records, list(cell.prohibited_fields)),
        "payloadHash": sha256_json(
            {"selectedFields": sorted(cell.selected_fields), "records": records}
        ),
        "releasePolicyHash": sha256_json(policy),
        "contractHash": payload["contractHash"],
        "expectedRelease": "RELEASED",
    }


def _dataset_labels(config: dict[str, Any], dataset_id: str) -> list[str]:
    return list(next(item for item in config["datasets"] if item["id"] == dataset_id)["labels"])


def _compute_schedule_rows(
    root: Path, config: dict[str, Any], task: str = TASK_A
) -> list[dict[str, Any]]:
    validate_matrix_config(root, config, task)
    model = config["models"][0]
    rows = [
        _schedule_row(root, config, model, cell) for cell in load_matrix_cells(root, config, task)
    ]
    for sequence, row in enumerate(rows, start=1):
        row["sequence"] = sequence
    return rows


def build_matrix_dry_run(research_root: Path, task: str = TASK_A) -> dict[str, Any]:
    """Build the offline schedule and its manifest; refuses existing artifacts."""
    config = _read_config(research_root, task)
    validate_matrix_config(research_root, config, task)
    schedule_path = research_root / SCHEDULE_PATHS[task]
    manifest_path = research_root / SCHEDULE_MANIFEST_PATHS[task]
    if schedule_path.exists() or manifest_path.exists():
        raise FileExistsError("matrix schedule artifacts already exist; append-only")
    schedule_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    rows = _compute_schedule_rows(research_root, config, task)
    schedule_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schedule_hash = sha256_json(rows)
    reservation_total = len(rows) * float(config["budget"]["reservation_per_call_eur"])
    budget = config["budget"]
    if reservation_total > float(budget["phase_authorized_eur"]):
        raise ValueError("reservation total exceeds the phase authorization")
    core = {
        "schemaVersion": "finboundbench.openrouter-purpose-selective-matrix-schedule.v3",
        "label": MATRIX_LABEL,
        "matrixId": config["matrix_id"],
        "task": task,
        "scope": config["scope"],
        "status": config["status"],
        "createdAt": _now(),
        "conditions": list(CONDITIONS),
        "datasets": [str(dataset["id"]) for dataset in config["datasets"]],
        "pairsPerDataset": 20,
        "repetitions": REPETITIONS,
        "cells": len(rows),
        "reservationTotalEur": round(reservation_total, 6),
        "phaseAuthorizedEur": float(budget["phase_authorized_eur"]),
        "absoluteAuthorizedEur": float(budget["absolute_authorized_eur"]),
        "modelLanes": [model["lane_id"] for model in config["models"]],
        "workloadImageDigest": config["workload_image_digest"],
        "scheduleHash": schedule_hash,
        "scheduleSha256": sha256_file(schedule_path),
        "scheduleBytes": schedule_path.stat().st_size,
    }
    manifest = {**core, "scheduleManifestHash": sha256_json(core)}
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def verify_matrix_dry_run(research_root: Path, task: str = TASK_A) -> dict[str, Any]:
    """Recompute the schedule from the config and compare against the artifacts."""
    config = _read_config(research_root, task)
    schedule_path = research_root / SCHEDULE_PATHS[task]
    manifest_path = research_root / SCHEDULE_MANIFEST_PATHS[task]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed = manifest.pop("scheduleManifestHash", None)
    if not isinstance(claimed, str) or sha256_json(manifest) != claimed:
        raise ValueError("matrix schedule manifest self-hash mismatch")
    manifest["scheduleManifestHash"] = claimed
    rows = json.loads(schedule_path.read_text(encoding="utf-8"))
    expected = _compute_schedule_rows(research_root, config, task)
    if rows != expected:
        raise ValueError("matrix schedule drift: recomputed schedule differs")
    if manifest["scheduleHash"] != sha256_json(rows):
        raise ValueError("matrix schedule hash mismatch")
    if manifest["scheduleSha256"] != sha256_file(schedule_path):
        raise ValueError("matrix schedule file hash mismatch")
    if manifest["cells"] != TOTAL_CELLS:
        raise ValueError("matrix schedule cell count mismatch")
    return manifest


def _artifact(root: Path, path: Path, repository: str) -> dict[str, Any]:
    absolute = root / path
    return {
        "repository": repository,
        "path": path.as_posix(),
        "sha256": sha256_file(absolute),
        "bytes": absolute.stat().st_size,
    }


def _model_manifest_artifacts(root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    return [_artifact(root, Path(model["manifest_path"]), "research") for model in config["models"]]


def _one_pair_anchor(research_root: Path) -> dict[str, Any]:
    manifest_path = research_root / ONE_PAIR_RUN_MANIFEST_PATH
    if not manifest_path.is_file():
        raise ValueError("validation anchor run manifest does not exist")
    run_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed = run_manifest.pop("manifestHash", None)
    if not isinstance(claimed, str) or sha256_json(run_manifest) != claimed:
        raise ValueError("one-pair validation run manifest self-hash mismatch")
    run_manifest["manifestHash"] = claimed
    if run_manifest.get("status") != "PASSED_ONE_PAIR_VALIDATION":
        raise ValueError("one-pair validation gate did not pass")
    return {
        "runManifestHash": claimed,
        "freezeManifestHash": run_manifest["freezeManifestHash"],
        "status": run_manifest["status"],
    }


def build_protocol_freeze(
    research_root: Path,
    platform_root: Path,
    *,
    research_commit: str,
    platform_commit: str,
) -> dict[str, Any]:
    """Freeze the corrected live protocol anchored on the one-pair gate."""
    schedule = {}
    for task in (TASK_A, TASK_B):
        config = _read_config(research_root, task)
        validate_matrix_config(research_root, config, task, require_live_authorization=True)
        rows = _compute_schedule_rows(research_root, config, task)
        schedule_path = research_root / SCHEDULE_PATHS[task]
        if not schedule_path.is_file():
            raise ValueError(f"task {task} schedule artifact does not exist")
        schedule[task] = {
            "path": SCHEDULE_PATHS[task].as_posix(),
            "scheduleHash": sha256_json(rows),
            "scheduleSha256": sha256_file(schedule_path),
            "cells": len(rows),
        }
    config = _read_config(research_root, TASK_A)
    anchor = _one_pair_anchor(research_root)
    artifacts = [
        *(_artifact(research_root, path, "research") for path in RESEARCH_ARTIFACTS),
        *_model_manifest_artifacts(research_root, config),
        *(_artifact(platform_root, path, "platform") for path in PLATFORM_ARTIFACTS),
    ]
    budget = config["budget"]
    core = {
        "schemaVersion": "finboundbench.protocol-v3-live-freeze",
        "matrixIds": [MATRIX_IDS[task] for task in (TASK_A, TASK_B)],
        "protocolId": config["protocol_id"],
        "status": "FROZEN_LIVE_PROTOCOL",
        "authorizationState": "LIVE_EXECUTION_AUTHORIZED",
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
        "validationAnchor": anchor,
        "schedule": schedule,
        "remoteProviderCallsPermitted": TOTAL_CELLS * 2,
        "providerSecretPermitted": True,
        "secretSource": "ENVIRONMENT_REFERENCE_ONLY",
        "awsActionsPermitted": False,
        "confirmatoryClaimsPermitted": False,
        "hardwareAttestation": False,
        "budget": {
            "ledgerPath": budget["ledger_path"],
            "authorizationId": budget["authorization_id"],
            "authorizationBasis": budget["authorization_basis"],
            "reservationPerCallEur": float(budget["reservation_per_call_eur"]),
            "phaseAuthorizedEur": float(budget["phase_authorized_eur"]),
            "absoluteAuthorizedEur": float(budget["absolute_authorized_eur"]),
        },
        "modelManifestHashes": [model["expected_manifest_hash"] for model in config["models"]],
        "artifacts": artifacts,
    }
    return {**core, "freezeManifestHash": sha256_json(core)}


def verify_protocol_freeze(research_root: Path, platform_root: Path) -> dict[str, Any]:
    for task in (TASK_A, TASK_B):
        config = _read_config(research_root, task)
        validate_matrix_config(research_root, config, task)
        rows = _compute_schedule_rows(research_root, config, task)
        schedule_path = research_root / SCHEDULE_PATHS[task]
        if not schedule_path.is_file() or sha256_file(schedule_path) != _schedule_file_sha(
            research_root, task
        ):
            raise ValueError(f"task {task} schedule file drift")
        if sha256_json(rows) != _schedule_hash_of(research_root, task):
            raise ValueError(f"task {task} schedule drift")
    path = research_root / PROTOCOL_FREEZE_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    claimed_hash = value.pop("freezeManifestHash", None)
    if not isinstance(claimed_hash, str) or sha256_json(value) != claimed_hash:
        raise ValueError("protocol freeze self-hash mismatch")
    value["freezeManifestHash"] = claimed_hash
    bindings = value["repositoryBindings"]
    if not _is_ancestor(research_root, bindings["researchCommit"]):
        raise ValueError("frozen research commit is not an ancestor of HEAD")
    if not _is_ancestor(platform_root, bindings["platformCommit"]):
        raise ValueError("frozen platform commit is not an ancestor of HEAD")
    frozen_schedule = value.get("schedule")
    if not isinstance(frozen_schedule, dict):
        raise TypeError("protocol freeze schedule section is missing")
    for task in (TASK_A, TASK_B):
        entry = frozen_schedule.get(task)
        if not isinstance(entry, dict):
            raise TypeError(f"protocol freeze schedule entry missing for {task}")
        if entry.get("scheduleHash") != _schedule_hash_of(research_root, task) or entry.get(
            "scheduleSha256"
        ) != _schedule_file_sha(research_root, task):
            raise ValueError(f"protocol freeze schedule drift for {task}")
    anchor = _one_pair_anchor(research_root)
    if value["validationAnchor"] != anchor:
        raise ValueError("protocol freeze validation anchor drift")
    roots = {"research": research_root, "platform": platform_root}
    for artifact in value["artifacts"]:
        artifact_path = roots[artifact["repository"]] / artifact["path"]
        if (
            artifact_path.stat().st_size != artifact["bytes"]
            or sha256_file(artifact_path) != artifact["sha256"]
        ):
            raise ValueError(f"frozen artifact changed: {artifact['path']}")
    return value


def _schedule_file_sha(research_root: Path, task: str) -> str:
    return sha256_file(research_root / SCHEDULE_PATHS[task])


def _schedule_hash_of(research_root: Path, task: str) -> str:
    return sha256_json(
        json.loads((research_root / SCHEDULE_PATHS[task]).read_text(encoding="utf-8"))
    )


def current_repository_bindings(research_root: Path, platform_root: Path) -> dict[str, str]:
    return {
        "researchCommit": git_commit(research_root),
        "platformCommit": git_commit(platform_root),
    }


def _append_chained(path: Path, core: dict[str, Any], previous: str) -> str:
    event = {**core, "previousEventHash": previous}
    event_hash = sha256_json(event)
    append_jsonl(path, {**event, "eventHash": event_hash})
    return event_hash


def _node_major() -> int:
    import re
    import subprocess

    completed = subprocess.run(["node", "--version"], capture_output=True, text=True, check=False)
    match = re.match(r"^v(\d+)\.", completed.stdout.strip())
    if not match:
        raise RuntimeError("node --version produced no usable version")
    return int(match.group(1))


def run_matrix(
    research_root: Path,
    platform_root: Path,
    task: str = TASK_A,
    *,
    resume: bool = False,
) -> dict[str, Any]:
    """Execute the task matrix live (paid, 1680 OpenRouter calls per task).

    With ``resume=True`` the driver continues an interrupted partial run:
    the existing hash-chained events are validated in full (chain linkage,
    ordering, contract hashes), then execution continues from the next
    sequence. The interrupted attempt's budget ledger is archived untouched
    and a fresh ledger is opened for the resumed portion, so every ledger
    record in the run manifest corresponds one-to-one with a released event.
    """
    import os
    import subprocess

    if _node_major() < NODE_MIN_MAJOR:
        raise RuntimeError(f"NODE_22_REQUIRED (found node v{_node_major()})")
    freeze = verify_protocol_freeze(research_root, platform_root)
    verify_matrix_dry_run(research_root, task)
    config = _read_config(research_root, task)
    validate_matrix_config(research_root, config, task, require_live_authorization=True)
    raw_path = research_root / config["raw_events_path"]
    manifest_path = research_root / config["run_manifest_path"]
    ledger_path = research_root / config["budget"]["ledger_path"]
    budget = config["budget"]
    model = config["models"][0]
    attempts = 0
    admitted = 0
    failed = 0
    previous = "0" * 64
    resumed_from = 0
    interrupted_ledger_archived: Path | None = None
    if resume:
        if not raw_path.is_file():
            raise FileExistsError("matrix run has no partial raw events to resume")
        if manifest_path.exists():
            raise FileExistsError("matrix run is already complete; append-only")
        existing = read_jsonl(raw_path)
        if not existing or len(existing) >= TOTAL_CELLS:
            raise ValueError("matrix partial run is empty or already complete")
        cells_all = load_matrix_cells(research_root, config, task)
        schedule_all = _compute_schedule_rows(research_root, config, task)
        for sequence, (event, cell, row) in enumerate(
            zip(existing, cells_all, schedule_all, strict=True), start=1
        ):
            event_hash = event.pop("eventHash", None)
            if event.get("previousEventHash") != previous or sha256_json(event) != event_hash:
                raise ValueError("matrix event chain mismatch in partial run")
            event["eventHash"] = event_hash
            previous = event_hash
            if (
                event["sequence"] != sequence
                or event["task"] != task
                or event["condition"] != cell.condition
                or event["variant"] != cell.variant
                or event["pairId"] != cell.pair_id
                or event["rep"] != cell.rep
                or event["contractHash"] != row["contractHash"]
            ):
                raise ValueError("matrix partial run ordering or contract mismatch")
            if event["status"] == "RELEASED":
                admitted += 1
            elif event["status"] == "FAILED":
                failed += 1
        attempts = len(existing)
        resumed_from = attempts
        if ledger_path.is_file():
            ledger_rows = read_jsonl(ledger_path)
            unsettled = {
                row["reservationId"]
                for row in ledger_rows
                if row.get("recordType") == "budget_reservation"
            } - {
                row["reservationId"]
                for row in ledger_rows
                if row.get("recordType") == "budget_settlement"
            }
            for reservation_id in sorted(unsettled):
                settle_budget(
                    ledger_path,
                    reservation_id=reservation_id,
                    model_id=model["expected_model_id"],
                    phase=f"MATRIX_REBUILD_{task.upper()}",
                    authorization_id=budget["authorization_id"],
                    budget_debit_eur=float(budget["reservation_per_call_eur"]),
                    outcome="interrupted_run",
                    provider_reported_cost=None,
                )
            archive = ledger_path.with_name(
                f"{ledger_path.stem}.interrupted-2026-08-06{ledger_path.suffix}"
            )
            ledger_path.replace(archive)
            interrupted_ledger_archived = archive
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        if raw_path.exists() or manifest_path.exists():
            raise FileExistsError("matrix run results already exist; append-only")
        if ledger_path.exists() and read_jsonl(ledger_path):
            raise FileExistsError("matrix ledger already has records; refusing to mix phases")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
    cells = load_matrix_cells(research_root, config, task)
    schedule = _compute_schedule_rows(research_root, config, task)
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    environment["FINBOUNDBENCH_ROOT"] = str(research_root)
    for sequence, (cell, row) in enumerate(
        zip(cells[attempts:], schedule[attempts:], strict=True), start=attempts + 1
    ):
        attempts += 1
        payload = build_matrix_bridge_payload(research_root, config, model, cell)
        if payload["contractHash"] != row["contractHash"]:
            raise ValueError("matrix schedule contract mismatch at execution time")
        started_at = _now()
        reservation_id = reserve_budget(
            ledger_path,
            model_id=model["expected_model_id"],
            phase=f"MATRIX_REBUILD_{task.upper()}",
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
                raise RuntimeError(
                    completed.stderr.strip() or f"bridge exit {completed.returncode}"
                )
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
                phase=f"MATRIX_REBUILD_{task.upper()}",
                authorization_id=budget["authorization_id"],
                budget_debit_eur=min(debit, float(budget["reservation_per_call_eur"])),
                outcome="passed" if released else "release_denied",
                provider_reported_cost=provider_reported_cost,
            )
        except Exception as error:  # noqa: BLE001 - every failure must become append-only evidence
            failed += 1
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
                phase=f"MATRIX_REBUILD_{task.upper()}",
                authorization_id=budget["authorization_id"],
                budget_debit_eur=float(budget["reservation_per_call_eur"]),
                outcome="failed_conservative_debit",
                provider_reported_cost=provider_reported_cost,
            )
        previous = _append_chained(
            raw_path,
            {
                "schemaVersion": "finboundbench.openrouter-purpose-selective-matrix-event.v3",
                "label": MATRIX_LABEL,
                "matrixId": config["matrix_id"],
                "task": task,
                "sequence": sequence,
                "dataset": cell.dataset,
                "condition": cell.condition,
                "variant": cell.variant,
                "pairId": cell.pair_id,
                "rep": cell.rep,
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
    interrupted_ledger = None
    if resume:
        if interrupted_ledger_archived is None:
            raise RuntimeError("resumed run lost its interrupted ledger archive")
        interrupted_rows = read_jsonl(interrupted_ledger_archived)
        interrupted_ledger = {
            "path": interrupted_ledger_archived.relative_to(research_root).as_posix(),
            "recordCount": len(interrupted_rows),
            "hash": sha256_json(interrupted_rows),
            "committedEur": committed_budget_eur(interrupted_rows),
            "events": resumed_from,
        }
    core = {
        "schemaVersion": "finboundbench.openrouter-purpose-selective-matrix-run.v3",
        "label": MATRIX_LABEL,
        "matrixId": config["matrix_id"],
        "task": task,
        "status": (
            "MATRIX_RUN_COMPLETE" if failed == 0 else "MATRIX_RUN_COMPLETE_WITH_RETAINED_FAILURES"
        ),
        "freezeManifestHash": freeze["freezeManifestHash"],
        "scheduleHash": sha256_json(schedule),
        "repositoryBindings": freeze["repositoryBindings"],
        "attempts": attempts,
        "released": admitted,
        "failedOrDenied": attempts - admitted,
        "finalEventHash": previous,
        "rawArtifact": raw_artifact,
        "resumedFromEvents": resumed_from if resume else None,
        "budget": {
            "ledgerPath": config["budget"]["ledger_path"],
            "ledgerRecordCount": len(ledger_rows),
            "ledgerHash": sha256_json(ledger_rows),
            "committedEur": committed_budget_eur(ledger_rows),
            "interruptedLedger": interrupted_ledger,
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
    return verify_matrix_run(research_root, platform_root, task)


def verify_matrix_run(
    research_root: Path, platform_root: Path, task: str = TASK_A
) -> dict[str, Any]:
    """Verify the task matrix run from raw evidence; fails closed on drift."""
    freeze = verify_protocol_freeze(research_root, platform_root)
    config = _read_config(research_root, task)
    validate_matrix_config(research_root, config, task, require_live_authorization=True)
    manifest_path = research_root / config["run_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed = manifest.pop("manifestHash", None)
    if not isinstance(claimed, str) or sha256_json(manifest) != claimed:
        raise ValueError("matrix run manifest self-hash mismatch")
    manifest["manifestHash"] = claimed
    if manifest["freezeManifestHash"] != freeze["freezeManifestHash"]:
        raise ValueError("matrix run is not bound to the active freeze")
    raw_path = research_root / manifest["rawArtifact"]["path"]
    if sha256_file(raw_path) != manifest["rawArtifact"]["sha256"]:
        raise ValueError("matrix raw artifact hash mismatch")
    events = read_jsonl(raw_path)
    if len(events) != manifest["attempts"] or len(events) != TOTAL_CELLS:
        raise ValueError("matrix event count mismatch")
    ledger_path = research_root / config["budget"]["ledger_path"]
    ledger_rows = read_jsonl(ledger_path)
    if (
        len(ledger_rows) != manifest["budget"]["ledgerRecordCount"]
        or sha256_json(ledger_rows) != manifest["budget"]["ledgerHash"]
    ):
        raise ValueError("matrix budget ledger changed after the run")
    if committed_budget_eur(ledger_rows) != manifest["budget"]["committedEur"]:
        raise ValueError("matrix committed budget mismatch")
    if committed_budget_eur(ledger_rows) > float(config["budget"]["absolute_authorized_eur"]):
        raise ValueError("matrix exceeded the absolute authorization")
    reservations = {
        row["reservationId"] for row in ledger_rows if row.get("recordType") == "budget_reservation"
    }
    settlements = {
        row["reservationId"] for row in ledger_rows if row.get("recordType") == "budget_settlement"
    }
    if reservations != settlements:
        raise ValueError("matrix reservations are not completely settled")
    resumed_from = manifest.get("resumedFromEvents")
    if resumed_from:
        interrupted = manifest["budget"].get("interruptedLedger")
        if not isinstance(interrupted, dict):
            raise ValueError("matrix resumed run lost its interrupted ledger record")
        interrupted_path = research_root / interrupted["path"]
        if not interrupted_path.is_file():
            raise ValueError("matrix interrupted ledger archive is missing")
        interrupted_rows = read_jsonl(interrupted_path)
        if (
            len(interrupted_rows) != interrupted["recordCount"]
            or sha256_json(interrupted_rows) != interrupted["hash"]
        ):
            raise ValueError("matrix interrupted ledger changed after the run")
        interrupted_r = {
            row["reservationId"]
            for row in interrupted_rows
            if row.get("recordType") == "budget_reservation"
        }
        interrupted_s = {
            row["reservationId"]
            for row in interrupted_rows
            if row.get("recordType") == "budget_settlement"
        }
        if interrupted_r != interrupted_s:
            raise ValueError("matrix interrupted ledger is not completely settled")
        orphan_settlements = [
            row
            for row in interrupted_rows
            if row.get("recordType") == "budget_settlement"
            and row.get("outcome") == "interrupted_run"
        ]
        if len(interrupted_r) != interrupted["events"] + len(orphan_settlements):
            raise ValueError("matrix interrupted ledger reservation count mismatch")
        if committed_budget_eur(interrupted_rows) != interrupted["committedEur"]:
            raise ValueError("matrix interrupted ledger committed mismatch")
        if committed_budget_eur(interrupted_rows) + committed_budget_eur(ledger_rows) > float(
            config["budget"]["absolute_authorized_eur"]
        ):
            raise ValueError("matrix combined committed budget exceeded the authorization")
        if len(reservations) != TOTAL_CELLS - resumed_from:
            raise ValueError("matrix resumed ledger reservation count mismatch")
    elif len(reservations) != len(events):
        raise ValueError("matrix reservations are not completely settled")
    cells = load_matrix_cells(research_root, config, task)
    schedule = _compute_schedule_rows(research_root, config, task)
    if manifest["scheduleHash"] != sha256_json(schedule):
        raise ValueError("matrix run schedule hash mismatch")
    previous = "0" * 64
    released = 0
    released_events: list[dict[str, Any]] = []
    by_approved_payload: dict[tuple[str, str, str], set[str]] = {}
    by_payload: dict[tuple[str, str, str], set[str]] = {}
    for sequence, (event, cell, row) in enumerate(
        zip(events, cells, schedule, strict=True), start=1
    ):
        event_hash = event.pop("eventHash", None)
        if event.get("previousEventHash") != previous or sha256_json(event) != event_hash:
            raise ValueError("matrix event chain mismatch")
        event["eventHash"] = event_hash
        previous = event_hash
        if (
            event["sequence"] != sequence
            or event["task"] != task
            or event["condition"] != cell.condition
            or event["variant"] != cell.variant
            or event["pairId"] != cell.pair_id
            or event["rep"] != cell.rep
        ):
            raise ValueError("matrix execution ordering mismatch")
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
            raise ValueError("matrix safety invariant failed")
        if (
            event["advertisedSelectedFields"] != list(cell.selected_fields)
            or event["advertisedApprovedFields"] != list(cell.approved_fields)
            or event["advertisedProhibitedFields"] != list(cell.prohibited_fields)
            or event["datasetProhibitedFields"] != list(cell.dataset_prohibited_fields)
            or event["groundTruth"] != cell.ground_truth
            or event["contractHash"] != row["contractHash"]
        ):
            raise ValueError("matrix advertised partition, truth, or contract mismatch")
        if (
            event["condition"] in ("B0", "B1")
            and event["advertisedProhibitedFields"] != event["datasetProhibitedFields"]
        ):
            raise ValueError("B0/B1 must transmit every dataset-prohibited field")
        if event["condition"] not in ("B0", "B1") and event["advertisedProhibitedFields"]:
            raise ValueError("approved-only conditions must transmit no prohibited field")
        if event["status"] == "RELEASED":
            result = event["result"]
            evidence = result["evidence"]
            release = result["nativeRelease"]
            if evidence["destinationHost"] != "openrouter.ai":
                raise ValueError("observed OpenRouter destination mismatch")
            if evidence["processingClassification"] != "REMOTE_PROVIDER_PROCESSING":
                raise ValueError("processing classification is not remote")
            if evidence["contractHash"] != event["contractHash"]:
                raise ValueError("matrix evidence contract mismatch")
            if evidence["transmittedFields"] != list(cell.selected_fields):
                raise ValueError("matrix evidence projection mismatch")
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
            if event["decision"] not in list(_dataset_labels(config, cell.dataset)):
                raise ValueError("released execution returned an invalid decision")
            released += 1
            released_events.append(event)
            by_approved_payload.setdefault((cell.dataset, cell.pair_id, cell.variant), set()).add(
                evidence["approvedPayloadHash"]
            )
            if cell.condition not in ("B0", "B1"):
                by_payload.setdefault((cell.dataset, cell.pair_id, cell.variant), set()).add(
                    evidence["payloadHash"]
                )
    if len(released_events) != TOTAL_CELLS:
        raise ValueError(f"matrix did not release all cells: {len(released_events)}")
    if resumed_from:
        interrupted_r = {
            row["reservationId"]
            for row in interrupted_rows
            if row.get("recordType") == "budget_reservation"
        }
        interrupted_s = {
            row["reservationId"]
            for row in interrupted_rows
            if row.get("recordType") == "budget_settlement"
        }
        interrupted_event_ids = {event["reservationId"] for event in events[:resumed_from]}
        if not interrupted_event_ids <= interrupted_s or len(interrupted_event_ids) != resumed_from:
            raise ValueError("matrix interrupted events are not fully settled in their ledger")
        resumed_event_ids = {event["reservationId"] for event in events[resumed_from:]}
        if (
            not resumed_event_ids <= settlements
            or len(resumed_event_ids) != TOTAL_CELLS - resumed_from
        ):
            raise ValueError("matrix resumed events are not fully settled in their ledger")
    for key, hashes in by_approved_payload.items():
        if len(hashes) != 1:
            raise ValueError(f"approved projection drifted across conditions: {key}")
    for key, hashes in by_payload.items():
        if len(hashes) != 1:
            raise ValueError(f"payload drifted across approved-only conditions: {key}")
    if previous != manifest["finalEventHash"] or released != manifest["released"]:
        raise ValueError("matrix summary mismatch")
    text = raw_path.read_text(encoding="utf-8").lower()
    if any(marker.lower() in text for marker in FORBIDDEN_SECRET_MARKERS):
        raise ValueError("provider secret marker found in matrix evidence")
    return manifest
