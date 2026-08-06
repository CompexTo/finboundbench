from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from purposebench.utils import sha256_json
from purposebench.v3.matrix import (
    CONDITIONS,
    CONFIG_PATH,
    FULL_POLICY,
    MATRIX_LABEL,
    RESEARCH_ARTIFACTS,
    TOTAL_CELLS,
    _one_pair_anchor,
    _schedule_row,
    build_matrix_bridge_payload,
    build_matrix_dry_run,
    build_protocol_freeze,
    composed_system_prompt,
    load_matrix_cells,
    matrix_release_policy,
    validate_matrix_config,
    verify_matrix_dry_run,
)
from purposebench.v3.tasks import (
    ESCALATED_REVIEW,
    PRIORITY_REVIEW,
    STANDARD_REVIEW,
    cfpb_complaint_routing_ground_truth,
    hmda_review_routing_ground_truth,
)

ROOT = Path(__file__).parents[2]
PLATFORM_ROOT = ROOT.parents[1]


def _config() -> dict:
    return yaml.safe_load((ROOT / CONFIG_PATH).read_text(encoding="utf-8"))


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


def test_config_passes_validation_against_the_current_repository() -> None:
    validate_matrix_config(ROOT, _config())


def test_config_validation_fails_closed_when_live_execution_is_permitted() -> None:
    config = _config()
    config["live_execution_permitted"] = True
    with pytest.raises(ValueError, match="MATRIX_LIVE_EXECUTION_NOT_AUTHORIZED"):
        validate_matrix_config(ROOT, config)


def test_config_validation_fails_closed_on_status_drift() -> None:
    config = _config()
    config["status"] = "AUTHORIZED_FOR_LIVE_EXECUTION"
    with pytest.raises(ValueError):
        validate_matrix_config(ROOT, config)


def test_config_validation_fails_closed_on_condition_drift() -> None:
    config = _config()
    config["conditions"] = config["conditions"][:6]
    with pytest.raises(ValueError, match="seven"):
        validate_matrix_config(ROOT, config)
    config = _config()
    config["conditions"][0]["policy"] = FULL_POLICY
    with pytest.raises(ValueError, match="pinned spec"):
        validate_matrix_config(ROOT, config)


def test_config_validation_fails_closed_on_repetition_change() -> None:
    config = _config()
    config["repetitions"] = 2
    with pytest.raises(ValueError, match="exactly 3"):
        validate_matrix_config(ROOT, config)


def test_config_validation_fails_closed_on_budget_envelope() -> None:
    config = _config()
    config["budget"]["absolute_authorized_eur"] = 1000.0
    with pytest.raises(ValueError):
        validate_matrix_config(ROOT, config)
    config = _config()
    config["budget"]["authorization_basis"] = "OTHER_INSTRUCTION"
    with pytest.raises(ValueError, match="authorization basis"):
        validate_matrix_config(ROOT, config)


def test_config_validation_fails_closed_on_denied_field_drift() -> None:
    config = _config()
    config["denied_fields"] = config["denied_fields"][:5]
    with pytest.raises(ValueError, match="denied fields"):
        validate_matrix_config(ROOT, config)


def test_config_validation_fails_closed_without_derived_prohibited_values() -> None:
    config = _config()
    config["datasets"][0]["prohibited_exact_values_derived_from"] = "hand_listed"
    with pytest.raises(ValueError, match="derived from the pair file"):
        validate_matrix_config(ROOT, config)


def test_config_validation_fails_closed_on_unknown_ground_truth() -> None:
    config = _config()
    config["datasets"][1]["ground_truth"] = "some_other_function"
    with pytest.raises(ValueError, match="ground truth"):
        validate_matrix_config(ROOT, config)


def test_config_validation_fails_closed_on_schema_vocabulary_drift() -> None:
    config = _config()
    config["response_schemas"]["cfpb"]["properties"]["decision"]["enum"] = [
        ESCALATED_REVIEW,
        STANDARD_REVIEW,
        "UNKNOWN",
    ]
    with pytest.raises(ValueError, match="decision vocabulary"):
        validate_matrix_config(ROOT, config)


def test_config_validation_fails_closed_on_bridge_digest_drift(
    tmp_root: Path,
) -> None:
    bridge = tmp_root / "scripts/governed_openrouter_pair_bridge_v3.cjs"
    bridge.write_text(bridge.read_text(encoding="utf-8") + "\n// tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="workload digest"):
        validate_matrix_config(tmp_root, _config())


def test_load_cells_returns_exactly_the_expected_matrix_shape() -> None:
    config = _config()
    cells = load_matrix_cells(ROOT, config)
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
    cells = load_matrix_cells(ROOT, _config())
    for condition in CONDITIONS:
        key = ("hmda", condition, "A", "hmda-3db69b9df2860cbe2a5c")
        reps = [c.rep for c in cells if (c.dataset, c.condition, c.variant, c.pair_id) == key]
        assert reps == [1, 2, 3]


def test_b0_transmits_the_full_record_including_prohibited_fields() -> None:
    cells = load_matrix_cells(ROOT, _config())
    for cell in cells:
        if cell.condition == "B0":
            assert list(cell.selected_fields) == sorted(cell.records[0].keys())
            assert set(cell.selected_fields) >= set(cell.approved_fields)
            assert cell.prohibited_fields == cell.dataset_prohibited_fields
        elif cell.condition in ("B2", "P0", "P1", "P2", "P3"):
            assert cell.selected_fields == cell.approved_fields
            assert cell.prohibited_fields == ()


def test_approved_projection_is_identical_across_conditions_and_variants() -> None:
    config = _config()
    cells = load_matrix_cells(ROOT, config)
    b0 = next(c for c in cells if c.condition == "B0" and c.dataset == "hmda" and c.variant == "A")
    p3 = next(c for c in cells if c.condition == "P3" and c.dataset == "hmda" and c.variant == "A")
    assert b0.approved_fields == p3.approved_fields
    assert sha256_json(
        [{f: r.get(f) for f in sorted(b0.approved_fields)} for r in b0.records]
    ) == sha256_json([{f: r.get(f) for f in sorted(p3.approved_fields)} for r in p3.records])


def test_ground_truth_matches_the_pinned_task_functions() -> None:
    cells = load_matrix_cells(ROOT, _config())
    for cell in cells[:40]:
        approved_only = {f: cell.records[0][f] for f in cell.approved_fields}
        if cell.dataset == "hmda":
            assert cell.ground_truth == hmda_review_routing_ground_truth(approved_only)
        else:
            assert cell.ground_truth == cfpb_complaint_routing_ground_truth(approved_only)
        assert cell.ground_truth in (
            PRIORITY_REVIEW,
            STANDARD_REVIEW,
            ESCALATED_REVIEW,
        )


def test_schedule_orders_executions_deterministically() -> None:
    config = _config()
    model = config["models"][0]
    cells = load_matrix_cells(ROOT, config)
    rows = [_schedule_row(ROOT, config, model, cell) for cell in cells]
    for sequence, row in enumerate(rows, start=1):
        row["sequence"] = sequence
    expected = [c.condition for c in cells]
    assert expected == [condition for condition in CONDITIONS for _ in range(240)]


def test_release_policy_validator_sets_per_condition() -> None:
    config = _config()
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
    config = _config()
    hmda = matrix_release_policy(ROOT, config, "hmda", "P3")
    cfpb = matrix_release_policy(ROOT, config, "cfpb", "P3")
    assert len(hmda["prohibitedExactValues"]["values"]) == 50
    assert len(cfpb["prohibitedExactValues"]["values"]) == 50
    assert "SYNTHETIC_ACTIVE_REVIEW" in hmda["prohibitedExactValues"]["values"]
    assert all(value.startswith("SYNTHETIC_") for value in hmda["prohibitedExactValues"]["values"])
    assert sorted(hmda["prohibitedFieldNames"]["names"]) == sorted(config["denied_fields"])


def test_purpose_clause_is_attached_only_to_purpose_conditions() -> None:
    config = _config()
    base = composed_system_prompt(config, "B0")
    assert config["prompts"]["purpose_clause"] not in base
    for condition in ("B1", "P0", "P1", "P2", "P3"):
        composed = composed_system_prompt(config, condition)
        assert composed.startswith(base)
        assert config["prompts"]["purpose_clause"] in composed


def test_bridge_payload_is_deterministic_and_carries_the_partition() -> None:
    config = _config()
    model = config["models"][0]
    cells = load_matrix_cells(ROOT, config)
    first = cells[0]
    payload_a = build_matrix_bridge_payload(ROOT, config, model, first)
    payload_b = build_matrix_bridge_payload(ROOT, config, model, first)
    assert payload_a["contractHash"] == payload_b["contractHash"]
    assert payload_a["contractHash"] == _schedule_row(ROOT, config, model, first)["contractHash"]
    assert payload_a["projectionClassification"] == {
        "approvedFields": sorted(first.approved_fields),
        "prohibitedFields": sorted(first.prohibited_fields),
    }
    assert payload_a["responseSchema"] == config["response_schemas"]["hmda"]
    assert payload_a["maximumAuthorizedCostEur"] == config["budget"]["reservation_per_call_eur"]


def test_p3_variants_are_byte_identical_and_b0_variants_differ() -> None:
    config = _config()
    model = config["models"][0]
    cells = load_matrix_cells(ROOT, config)
    rows = [_schedule_row(ROOT, config, model, cell) for cell in cells]
    p3_a = next(
        r for r in rows if r["condition"] == "P3" and r["variant"] == "A" and r["dataset"] == "hmda"
    )
    p3_b = next(
        r for r in rows if r["condition"] == "P3" and r["variant"] == "B" and r["dataset"] == "hmda"
    )
    b0_a = next(
        r for r in rows if r["condition"] == "B0" and r["variant"] == "A" and r["dataset"] == "hmda"
    )
    b0_b = next(
        r for r in rows if r["condition"] == "B0" and r["variant"] == "B" and r["dataset"] == "hmda"
    )
    assert p3_a["approvedPayloadHash"] == p3_b["approvedPayloadHash"]
    assert p3_a["payloadHash"] == p3_b["payloadHash"]
    assert b0_a["approvedPayloadHash"] == b0_b["approvedPayloadHash"]
    assert b0_a["payloadHash"] != b0_b["payloadHash"]
    assert b0_a["prohibitedPayloadHash"] != b0_b["prohibitedPayloadHash"]
    assert p3_a["prohibitedPayloadHash"] == p3_b["prohibitedPayloadHash"]


def test_dry_run_builds_and_verifies_hermetically(tmp_root: Path) -> None:
    manifest = build_matrix_dry_run(tmp_root)
    assert manifest["cells"] == TOTAL_CELLS
    assert manifest["label"] == MATRIX_LABEL
    assert manifest["status"] == "SCHEDULED_LIVE_EXECUTION_NOT_AUTHORIZED"
    assert manifest["reservationTotalEur"] == round(TOTAL_CELLS * 0.02, 6)
    assert manifest["reservationTotalEur"] <= manifest["phaseAuthorizedEur"]
    verified = verify_matrix_dry_run(tmp_root)
    assert verified["scheduleHash"] == manifest["scheduleHash"]
    rows = json.loads(
        (tmp_root / "results/v3/matrix-rebuild/manifests/schedule.json").read_text(encoding="utf-8")
    )
    assert len(rows) == TOTAL_CELLS
    assert len({row["contractHash"] for row in rows}) == TOTAL_CELLS


def test_dry_run_refuses_to_overwrite_existing_artifacts(tmp_root: Path) -> None:
    build_matrix_dry_run(tmp_root)
    with pytest.raises(FileExistsError):
        build_matrix_dry_run(tmp_root)


def test_protocol_freeze_builds_against_the_tmp_schedule(tmp_root: Path) -> None:
    schedule = build_matrix_dry_run(tmp_root)
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
    assert freeze["schedule"]["scheduleHash"] == schedule["scheduleHash"]
    assert freeze["schedule"]["cells"] == TOTAL_CELLS
    assert freeze["validationAnchor"]["status"] == "PASSED_ONE_PAIR_VALIDATION"
    assert freeze["remoteProviderCallsPermitted"] == TOTAL_CELLS
    assert freeze["confirmatoryClaimsPermitted"] is False
    assert freeze["hardwareAttestation"] is False
    research_paths = {a["path"] for a in freeze["artifacts"] if a["repository"] == "research"}
    assert CONFIG_PATH.as_posix() in research_paths
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
