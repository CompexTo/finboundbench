from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from purposebench.utils import sha256_json
from purposebench.v3.matrix import (
    CONDITIONS,
    CONFIG_PATHS,
    FULL_POLICY,
    MATRIX_LABEL,
    RESEARCH_ARTIFACTS,
    TASK_A,
    TASK_B,
    TOTAL_CELLS,
    _append_chained,
    _one_pair_anchor,
    _schedule_row,
    build_matrix_bridge_payload,
    build_matrix_dry_run,
    build_protocol_freeze,
    composed_system_prompt,
    load_matrix_cells,
    matrix_release_policy,
    run_matrix,
    validate_matrix_config,
    verify_matrix_dry_run,
    verify_matrix_run,
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

ROOT = Path(__file__).parents[2]
PLATFORM_ROOT = ROOT.parents[1]


def _config(task: str = TASK_A) -> dict:
    return yaml.safe_load((ROOT / CONFIG_PATHS[task]).read_text(encoding="utf-8"))


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    for relative in (
        *tuple(path.as_posix() for path in RESEARCH_ARTIFACTS),
        "data/v2/generated/hmda-2024-dc-pairs.jsonl",
        "data/v2/generated/cfpb-2024-01-dc-pairs.jsonl",
        "docs/v3/model-manifests/openrouter-google-gemma-4-26b-a4b-it.json",
        "results/v3/pair-validation/manifests/run-manifest.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    return tmp_path


def _authorize_tmp_configs(tmp_root: Path) -> None:
    for task in (TASK_A, TASK_B):
        config_path = tmp_root / CONFIG_PATHS[task]
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["live_execution_permitted"] = True
        config["status"] = "LIVE_EXECUTION_AUTHORIZED"
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def test_config_passes_validation_against_the_current_repository() -> None:
    validate_matrix_config(ROOT, _config(TASK_A), TASK_A)
    validate_matrix_config(ROOT, _config(TASK_B), TASK_B)


def test_config_passes_validation_with_live_authorization() -> None:
    validate_matrix_config(ROOT, _config(TASK_A), TASK_A, require_live_authorization=True)
    validate_matrix_config(ROOT, _config(TASK_B), TASK_B, require_live_authorization=True)


def test_config_validation_fails_closed_on_partial_authorization() -> None:
    config = _config(TASK_A)
    config["live_execution_permitted"] = False
    with pytest.raises(ValueError, match="SCHEDULED_LIVE_EXECUTION_NOT_AUTHORIZED"):
        validate_matrix_config(ROOT, config, TASK_A)
    config = _config(TASK_A)
    config["status"] = "SCHEDULED_LIVE_EXECUTION_NOT_AUTHORIZED"
    with pytest.raises(ValueError, match="LIVE_EXECUTION_AUTHORIZED"):
        validate_matrix_config(ROOT, config, TASK_A)


def test_config_validation_fails_closed_on_status_drift() -> None:
    config = _config(TASK_A)
    config["status"] = "AUTHORIZED_FOR_LIVE_EXECUTION"
    with pytest.raises(ValueError):
        validate_matrix_config(ROOT, config, TASK_A)


def test_config_validation_fails_closed_on_condition_drift() -> None:
    config = _config(TASK_A)
    config["conditions"] = config["conditions"][:6]
    with pytest.raises(ValueError, match="seven"):
        validate_matrix_config(ROOT, config, TASK_A)
    config = _config(TASK_A)
    config["conditions"][0]["policy"] = FULL_POLICY
    with pytest.raises(ValueError, match="pinned spec"):
        validate_matrix_config(ROOT, config, TASK_A)


def test_config_validation_fails_closed_on_repetition_change() -> None:
    config = _config(TASK_A)
    config["repetitions"] = 2
    with pytest.raises(ValueError, match="exactly 3"):
        validate_matrix_config(ROOT, config, TASK_A)


def test_config_validation_fails_closed_on_budget_envelope() -> None:
    config = _config(TASK_A)
    config["budget"]["absolute_authorized_eur"] = 1000.0
    with pytest.raises(ValueError):
        validate_matrix_config(ROOT, config, TASK_A)
    config = _config(TASK_A)
    config["budget"]["authorization_basis"] = "OTHER_INSTRUCTION"
    with pytest.raises(ValueError, match="authorization basis"):
        validate_matrix_config(ROOT, config, TASK_A)


def test_config_validation_fails_closed_on_denied_field_drift() -> None:
    config = _config(TASK_A)
    config["denied_fields"] = config["denied_fields"][:5]
    with pytest.raises(ValueError, match="denied fields"):
        validate_matrix_config(ROOT, config, TASK_A)


def test_config_validation_fails_closed_without_derived_prohibited_values() -> None:
    config = _config(TASK_A)
    config["datasets"][0]["prohibited_exact_values_derived_from"] = "hand_listed"
    with pytest.raises(ValueError, match="derived from the pair file"):
        validate_matrix_config(ROOT, config, TASK_A)


def test_config_validation_fails_closed_on_unknown_ground_truth() -> None:
    config = _config(TASK_A)
    config["datasets"][1]["ground_truth"] = "some_other_function"
    with pytest.raises(ValueError, match="ground truth"):
        validate_matrix_config(ROOT, config, TASK_A)


def test_config_validation_fails_closed_on_schema_vocabulary_drift() -> None:
    config = _config(TASK_A)
    config["response_schemas"]["cfpb"]["properties"]["decision"]["enum"] = [
        ESCALATED_REVIEW,
        STANDARD_REVIEW,
        "UNKNOWN",
    ]
    with pytest.raises(ValueError, match="decision vocabulary"):
        validate_matrix_config(ROOT, config, TASK_A)


def test_config_validation_fails_closed_on_bridge_digest_drift(
    tmp_root: Path,
) -> None:
    bridge = tmp_root / "scripts/governed_openrouter_pair_bridge_v3.cjs"
    bridge.write_text(bridge.read_text(encoding="utf-8") + "\n// tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="workload digest"):
        validate_matrix_config(tmp_root, _config(TASK_A), TASK_A)


def test_taskb_config_validation_fails_closed_when_task_id_is_wrong() -> None:
    config = _config(TASK_B)
    config["task_id"] = "taskA"
    with pytest.raises(ValueError, match="does not belong"):
        validate_matrix_config(ROOT, config, TASK_B)


def test_taskb_config_validation_fails_closed_on_matrix_id_drift() -> None:
    config = _config(TASK_B)
    config["matrix_id"] = "finboundbench-v3-purpose-selective-matrix"
    with pytest.raises(ValueError, match="matrix_id"):
        validate_matrix_config(ROOT, config, TASK_B)


def test_taskb_config_validation_fails_closed_on_label_drift() -> None:
    config = _config(TASK_B)
    config["datasets"][0]["labels"] = [PRIORITY_REVIEW, STANDARD_REVIEW]
    with pytest.raises(ValueError, match="labels changed"):
        validate_matrix_config(ROOT, config, TASK_B)


def test_cross_task_consistency_fails_closed_on_pair_file_drift(tmp_root: Path) -> None:
    config = _config(TASK_B)
    config["datasets"][0]["pair_file"] = "data/v2/generated/cfpb-2024-01-dc-pairs.jsonl"
    with pytest.raises(ValueError, match="pair file"):
        validate_matrix_config(tmp_root, config, TASK_B)


def test_cross_task_consistency_fails_closed_on_prompt_drift(tmp_root: Path) -> None:
    config = _config(TASK_B)
    config["prompts"]["purpose_clause"] = "Purpose: tampered."
    with pytest.raises(ValueError, match="prompts.purpose_clause"):
        validate_matrix_config(tmp_root, config, TASK_B)


def test_cross_task_consistency_fails_closed_on_seed_drift(tmp_root: Path) -> None:
    config = _config(TASK_B)
    config["seed"] = "another-seed"
    with pytest.raises(ValueError, match="seed"):
        validate_matrix_config(tmp_root, config, TASK_B)


def test_cross_task_consistency_fails_closed_on_budget_envelope_drift(
    tmp_root: Path,
) -> None:
    config = _config(TASK_B)
    config["budget"]["reservation_per_call_eur"] = 0.03
    with pytest.raises(ValueError, match="budget.reservation"):
        validate_matrix_config(tmp_root, config, TASK_B)


def test_cross_task_consistency_fails_closed_on_condition_drift(tmp_root: Path) -> None:
    config = _config(TASK_B)
    config["conditions"][0]["rule_suffix"] = "tampered"
    with pytest.raises(ValueError):
        validate_matrix_config(tmp_root, config, TASK_B)


def test_load_cells_returns_exactly_the_expected_matrix_shape() -> None:
    for task in (TASK_A, TASK_B):
        config = _config(task)
        cells = load_matrix_cells(ROOT, config, task)
        assert len(cells) == TOTAL_CELLS
        assert cells[0].dataset == "hmda"
        assert cells[0].condition == "B0"
        assert cells[0].variant == "A"
        assert cells[0].rep == 1
        assert cells[-1].dataset == "cfpb"
        assert cells[-1].condition == "P3"
        assert cells[-1].variant == "B"
        assert cells[-1].rep == 3
        per_condition = {
            condition: sum(c.condition == condition for c in cells) for condition in CONDITIONS
        }
        assert per_condition == {condition: 240 for condition in CONDITIONS}
        assert {c.dataset for c in cells} == {"hmda", "cfpb"}


def test_every_cell_has_all_repetitions() -> None:
    for task in (TASK_A, TASK_B):
        cells = load_matrix_cells(ROOT, _config(task), task)
        for condition in CONDITIONS:
            key = ("hmda", condition, "A", "hmda-3db69b9df2860cbe2a5c")
            reps = [c.rep for c in cells if (c.dataset, c.condition, c.variant, c.pair_id) == key]
            assert reps == [1, 2, 3]


def test_b0_transmits_the_full_record_including_prohibited_fields() -> None:
    for task in (TASK_A, TASK_B):
        cells = load_matrix_cells(ROOT, _config(task), task)
        for cell in cells:
            if cell.condition == "B0":
                assert list(cell.selected_fields) == sorted(cell.records[0].keys())
                assert set(cell.selected_fields) >= set(cell.approved_fields)
                assert cell.prohibited_fields == cell.dataset_prohibited_fields
            elif cell.condition in ("B2", "P0", "P1", "P2", "P3"):
                assert cell.selected_fields == cell.approved_fields
                assert cell.prohibited_fields == ()


def test_approved_projection_is_identical_across_conditions_and_variants() -> None:
    for task in (TASK_A, TASK_B):
        config = _config(task)
        cells = load_matrix_cells(ROOT, config, task)
        b0 = next(
            c for c in cells if c.condition == "B0" and c.dataset == "hmda" and c.variant == "A"
        )
        p3 = next(
            c for c in cells if c.condition == "P3" and c.dataset == "hmda" and c.variant == "A"
        )
        assert b0.approved_fields == p3.approved_fields
        assert sha256_json(
            [{f: r.get(f) for f in sorted(b0.approved_fields)} for r in b0.records]
        ) == sha256_json([{f: r.get(f) for f in sorted(p3.approved_fields)} for r in p3.records])


def test_ground_truth_matches_the_pinned_task_functions() -> None:
    expectations = {
        TASK_A: {
            "hmda": hmda_review_routing_ground_truth,
            "cfpb": cfpb_complaint_routing_ground_truth,
        },
        TASK_B: {"hmda": hmda_taskb_window_ground_truth, "cfpb": cfpb_taskb_queue_ground_truth},
    }
    for task in (TASK_A, TASK_B):
        cells = load_matrix_cells(ROOT, _config(task), task)
        for cell in cells[:40]:
            approved_only = {f: cell.records[0][f] for f in cell.approved_fields}
            assert cell.ground_truth == expectations[task][cell.dataset](approved_only)


def test_task_ground_truths_are_labeled_per_task() -> None:
    for cell in load_matrix_cells(ROOT, _config(TASK_A), TASK_A):
        assert cell.ground_truth in (
            PRIORITY_REVIEW,
            STANDARD_REVIEW,
            ESCALATED_REVIEW,
        )
    for cell in load_matrix_cells(ROOT, _config(TASK_B), TASK_B):
        assert cell.ground_truth in (
            ROUTINE_WINDOW,
            PRIORITY_WINDOW,
            STANDARD_QUEUE,
            PRIORITY_QUEUE,
        )


def test_task_ground_truths_have_sufficient_class_prevalence() -> None:
    for task in (TASK_A, TASK_B):
        cells = load_matrix_cells(ROOT, _config(task), task)
        for dataset in ("hmda", "cfpb"):
            labels = [c.ground_truth for c in cells if c.dataset == dataset]
            minority = min(labels.count(x) for x in set(labels))
            assert minority >= 6


def test_schedule_orders_executions_deterministically() -> None:
    for task in (TASK_A, TASK_B):
        config = _config(task)
        model = config["models"][0]
        cells = load_matrix_cells(ROOT, config, task)
        rows = [_schedule_row(ROOT, config, model, cell) for cell in cells]
        for sequence, row in enumerate(rows, start=1):
            row["sequence"] = sequence
        expected = [c.condition for c in cells]
        assert expected == [condition for condition in CONDITIONS for _ in range(240)]


def test_release_policy_validator_sets_per_condition() -> None:
    config = _config(TASK_A)
    minimal = matrix_release_policy(ROOT, config, "hmda", "B0")
    full = matrix_release_policy(ROOT, config, "hmda", "P3")
    assert (
        set(minimal["requiredValidators"])
        & {
            "compex.output.prohibited-exact-values",
            "compex.output.prohibited-field-names",
            "compex.output.pii-patterns",
        }
        == set()
    )
    assert set(full["requiredValidators"]) >= {
        "compex.output.prohibited-exact-values",
        "compex.output.prohibited-field-names",
        "compex.output.pii-patterns",
    }
    assert full["policyRuleId"] == "finboundbench-v3-matrix-full-purpose-selective"
    assert minimal["policyRuleId"] == "finboundbench-v3-matrix-no-purpose-binding"
    assert minimal["classificationEvidenceRequired"] is False
    assert full["classificationEvidenceRequired"] is True


def test_release_policy_derives_prohibited_values_from_the_pair_files() -> None:
    config = _config(TASK_A)
    hmda = matrix_release_policy(ROOT, config, "hmda", "P3")
    cfpb = matrix_release_policy(ROOT, config, "cfpb", "P3")
    assert len(hmda["prohibitedExactValues"]["values"]) == 50
    assert len(cfpb["prohibitedExactValues"]["values"]) == 50
    assert "SYNTHETIC_ACTIVE_REVIEW" in hmda["prohibitedExactValues"]["values"]
    assert all(value.startswith("SYNTHETIC_") for value in hmda["prohibitedExactValues"]["values"])
    assert sorted(hmda["prohibitedFieldNames"]["names"]) == sorted(config["denied_fields"])


def test_purpose_clause_is_attached_only_to_purpose_conditions() -> None:
    for task in (TASK_A, TASK_B):
        config = _config(task)
        base = composed_system_prompt(config, "B0")
        assert config["prompts"]["purpose_clause"] not in base
        for condition in ("B1", "P0", "P1", "P2", "P3"):
            composed = composed_system_prompt(config, condition)
            assert composed.startswith(base)
            assert config["prompts"]["purpose_clause"] in composed


def test_bridge_payload_is_deterministic_and_carries_the_partition() -> None:
    for task in (TASK_A, TASK_B):
        config = _config(task)
        model = config["models"][0]
        cells = load_matrix_cells(ROOT, config, task)
        first = cells[0]
        payload_a = build_matrix_bridge_payload(ROOT, config, model, first)
        payload_b = build_matrix_bridge_payload(ROOT, config, model, first)
        assert payload_a["contractHash"] == payload_b["contractHash"]
        assert (
            payload_a["contractHash"] == _schedule_row(ROOT, config, model, first)["contractHash"]
        )
        assert payload_a["projectionClassification"] == {
            "approvedFields": sorted(first.approved_fields),
            "prohibitedFields": sorted(first.prohibited_fields),
        }
        assert payload_a["responseSchema"] == config["response_schemas"]["hmda"]
        assert payload_a["maximumAuthorizedCostEur"] == config["budget"]["reservation_per_call_eur"]


def test_p3_variants_are_byte_identical_and_b0_variants_differ() -> None:
    for task in (TASK_A, TASK_B):
        config = _config(task)
        model = config["models"][0]
        cells = load_matrix_cells(ROOT, config, task)
        rows = [_schedule_row(ROOT, config, model, cell) for cell in cells]
        p3_a = next(
            r
            for r in rows
            if r["condition"] == "P3" and r["variant"] == "A" and r["dataset"] == "hmda"
        )
        p3_b = next(
            r
            for r in rows
            if r["condition"] == "P3" and r["variant"] == "B" and r["dataset"] == "hmda"
        )
        b0_a = next(
            r
            for r in rows
            if r["condition"] == "B0" and r["variant"] == "A" and r["dataset"] == "hmda"
        )
        b0_b = next(
            r
            for r in rows
            if r["condition"] == "B0" and r["variant"] == "B" and r["dataset"] == "hmda"
        )
        assert p3_a["approvedPayloadHash"] == p3_b["approvedPayloadHash"]
        assert p3_a["payloadHash"] == p3_b["payloadHash"]
        assert b0_a["approvedPayloadHash"] == b0_b["approvedPayloadHash"]
        assert b0_a["payloadHash"] != b0_b["payloadHash"]
        assert b0_a["prohibitedPayloadHash"] != b0_b["prohibitedPayloadHash"]
        assert p3_a["prohibitedPayloadHash"] == p3_b["prohibitedPayloadHash"]


def test_task_schedules_differ_in_ground_truth_but_share_payloads() -> None:
    config_a = _config(TASK_A)
    config_b = _config(TASK_B)
    model = config_a["models"][0]
    cells_a = load_matrix_cells(ROOT, config_a, TASK_A)
    cells_b = load_matrix_cells(ROOT, config_b, TASK_B)
    rows_a = [_schedule_row(ROOT, config_a, model, cell) for cell in cells_a]
    rows_b = [_schedule_row(ROOT, config_b, model, cell) for cell in cells_b]
    for row_a, row_b in zip(rows_a, rows_b, strict=True):
        assert row_a["payloadHash"] == row_b["payloadHash"]
        assert row_a["systemPromptHash"] == row_b["systemPromptHash"]
        assert row_a["userPromptHash"] != row_b["userPromptHash"]
        assert row_a["groundTruth"] != row_b["groundTruth"]
        assert row_a["contractHash"] != row_b["contractHash"]


def test_dry_run_builds_and_verifies_hermetically_for_both_tasks(tmp_root: Path) -> None:
    for task in (TASK_A, TASK_B):
        manifest = build_matrix_dry_run(tmp_root, task=task)
        assert manifest["cells"] == TOTAL_CELLS
        assert manifest["label"] == MATRIX_LABEL
        assert manifest["task"] == task
        assert manifest["status"] == "LIVE_EXECUTION_AUTHORIZED"
        assert manifest["reservationTotalEur"] == round(TOTAL_CELLS * 0.02, 6)
        assert manifest["reservationTotalEur"] <= manifest["phaseAuthorizedEur"]
        verified = verify_matrix_dry_run(tmp_root, task=task)
        assert verified["scheduleHash"] == manifest["scheduleHash"]
        schedule_relative = (
            "results/v3/matrix-rebuild/manifests/schedule.json"
            if task == TASK_A
            else "results/v3/matrix-rebuild/taskB/manifests/schedule.json"
        )
        rows = json.loads((tmp_root / schedule_relative).read_text(encoding="utf-8"))
        assert len(rows) == TOTAL_CELLS
        assert len({row["contractHash"] for row in rows}) == TOTAL_CELLS


def test_dry_run_refuses_to_overwrite_existing_artifacts(tmp_root: Path) -> None:
    build_matrix_dry_run(tmp_root, task=TASK_A)
    with pytest.raises(FileExistsError):
        build_matrix_dry_run(tmp_root, task=TASK_A)


def test_protocol_freeze_builds_against_the_tmp_schedules(tmp_root: Path) -> None:
    schedules = {
        TASK_A: build_matrix_dry_run(tmp_root, task=TASK_A),
        TASK_B: build_matrix_dry_run(tmp_root, task=TASK_B),
    }
    _authorize_tmp_configs(tmp_root)
    freeze = build_protocol_freeze(
        tmp_root,
        PLATFORM_ROOT,
        research_commit="a" * 40,
        platform_commit="b" * 40,
    )
    claimed = freeze.pop("freezeManifestHash")
    assert sha256_json(freeze) == claimed
    freeze["freezeManifestHash"] = claimed
    assert freeze["status"] == "FROZEN_LIVE_PROTOCOL"
    assert freeze["schedule"][TASK_A]["scheduleHash"] == schedules[TASK_A]["scheduleHash"]
    assert freeze["schedule"][TASK_B]["scheduleHash"] == schedules[TASK_B]["scheduleHash"]
    assert freeze["schedule"][TASK_A]["cells"] == TOTAL_CELLS
    assert freeze["schedule"][TASK_B]["cells"] == TOTAL_CELLS
    assert freeze["validationAnchor"]["status"] == "PASSED_ONE_PAIR_VALIDATION"
    assert freeze["remoteProviderCallsPermitted"] == TOTAL_CELLS * 2
    assert freeze["confirmatoryClaimsPermitted"] is False
    assert freeze["hardwareAttestation"] is False
    research_paths = {a["path"] for a in freeze["artifacts"] if a["repository"] == "research"}
    assert CONFIG_PATHS[TASK_A].as_posix() in research_paths
    assert CONFIG_PATHS[TASK_B].as_posix() in research_paths
    platform_artifacts = [a for a in freeze["artifacts"] if a["repository"] == "platform"]
    assert len(platform_artifacts) == 4
    assert len(freeze["modelManifestHashes"]) == 1


def test_protocol_freeze_anchors_on_the_one_pair_gate() -> None:
    anchor = _one_pair_anchor(ROOT)
    assert anchor["status"] == "PASSED_ONE_PAIR_VALIDATION"
    assert len(anchor["runManifestHash"]) == 64
    assert len(anchor["freezeManifestHash"]) == 64


def test_protocol_freeze_rejects_a_missing_validation_anchor(tmp_root: Path) -> None:
    (tmp_root / "results/v3/pair-validation/manifests/run-manifest.json").unlink()
    with pytest.raises(ValueError, match="validation anchor"):
        _one_pair_anchor(tmp_root)


def test_protocol_freeze_refuses_without_live_authorization(tmp_root: Path) -> None:
    build_matrix_dry_run(tmp_root, task=TASK_A)
    build_matrix_dry_run(tmp_root, task=TASK_B)
    for task in (TASK_A, TASK_B):
        config_path = tmp_root / CONFIG_PATHS[task]
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        config["live_execution_permitted"] = False
        config["status"] = "SCHEDULED_LIVE_EXECUTION_NOT_AUTHORIZED"
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="MATRIX_LIVE_EXECUTION_NOT_AUTHORIZED"):
        build_protocol_freeze(
            tmp_root,
            PLATFORM_ROOT,
            research_commit="a" * 40,
            platform_commit="b" * 40,
        )


def test_resume_refuses_when_no_partial_raw_events_exist(
    tmp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("purposebench.v3.matrix._node_major", lambda: 22)
    monkeypatch.setattr(
        "purposebench.v3.matrix.verify_protocol_freeze",
        lambda _root, _platform: {
            "freezeManifestHash": "f" * 64,
            "repositoryBindings": {},
        },
    )
    build_matrix_dry_run(tmp_root, task=TASK_A)
    build_matrix_dry_run(tmp_root, task=TASK_B)
    _authorize_tmp_configs(tmp_root)
    with pytest.raises(FileExistsError, match="no partial raw events"):
        run_matrix(tmp_root, PLATFORM_ROOT, task=TASK_A, resume=True)


def test_resume_refuses_when_partial_run_is_empty(
    tmp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("purposebench.v3.matrix._node_major", lambda: 22)
    monkeypatch.setattr(
        "purposebench.v3.matrix.verify_protocol_freeze",
        lambda _root, _platform: {
            "freezeManifestHash": "f" * 64,
            "repositoryBindings": {},
        },
    )
    build_matrix_dry_run(tmp_root, task=TASK_A)
    build_matrix_dry_run(tmp_root, task=TASK_B)
    _authorize_tmp_configs(tmp_root)
    raw_path = tmp_root / "results/v3/matrix-rebuild/raw/events.jsonl"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty or already complete"):
        run_matrix(tmp_root, PLATFORM_ROOT, task=TASK_A, resume=True)


def test_resume_rejects_a_broken_event_chain(
    tmp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("purposebench.v3.matrix._node_major", lambda: 22)
    monkeypatch.setattr(
        "purposebench.v3.matrix.verify_protocol_freeze",
        lambda _root, _platform: {
            "freezeManifestHash": "f" * 64,
            "repositoryBindings": {},
        },
    )
    build_matrix_dry_run(tmp_root, task=TASK_A)
    build_matrix_dry_run(tmp_root, task=TASK_B)
    _authorize_tmp_configs(tmp_root)
    rows = json.loads(
        (tmp_root / "results/v3/matrix-rebuild/manifests/schedule.json").read_text(encoding="utf-8")
    )

    def partial_event(row: dict) -> dict:
        return {
            "task": TASK_A,
            "sequence": row["sequence"],
            "condition": row["condition"],
            "variant": row["variant"],
            "pairId": row["pairId"],
            "rep": row["rep"],
            "contractHash": row["contractHash"],
            "status": "RELEASED",
        }

    raw_path = tmp_root / "results/v3/matrix-rebuild/raw/events.jsonl"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    _append_chained(raw_path, partial_event(rows[0]), "0" * 64)
    _append_chained(raw_path, partial_event(rows[1]), "0" * 64)
    with pytest.raises(ValueError, match="partial run"):
        run_matrix(tmp_root, PLATFORM_ROOT, task=TASK_A, resume=True)


def test_verify_accepts_the_completed_matrix_run_with_retained_outcomes() -> None:
    if not (ROOT / "results/v3/matrix-rebuild/manifests/run-manifest.json").is_file():
        pytest.skip("no completed matrix run artifacts on this checkout")
    manifest = verify_matrix_run(ROOT, PLATFORM_ROOT, task=TASK_A)
    assert manifest["status"] == "MATRIX_RUN_COMPLETE_WITH_RETAINED_FAILURES"
    assert manifest["released"] > 0
    assert manifest["resumedFromEvents"] == 1404
