from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from purposebench.v3.pair_validation import (
    build_pair_bridge_payload,
    load_cells,
    pair_release_policy,
    validate_pair_validation_config,
)
from purposebench.v3.tasks import PRIORITY_REVIEW, STANDARD_REVIEW
from purposebench.v3.transmission import ProjectionClassificationError

ROOT = Path(__file__).parents[2]


@pytest.fixture()
def config() -> dict[str, Any]:
    return _read_config()


def _read_config() -> dict[str, Any]:
    import yaml

    return yaml.safe_load((ROOT / "configs/v3/openrouter-one-pair-validation.yaml").read_text(encoding="utf-8"))


def test_config_passes_validation_against_live_bridge_digest() -> None:
    config = _read_config()
    from purposebench.utils import sha256_file

    expected = f"sha256:{sha256_file(ROOT / 'scripts/governed_openrouter_pair_bridge_v3.cjs')}"
    config["workload_image_digest"] = expected
    validate_pair_validation_config(ROOT, config)


def test_config_validation_fails_closed_on_digest_drift() -> None:
    config = _read_config()
    config["workload_image_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="workload digest"):
        validate_pair_validation_config(ROOT, config)


def test_config_validation_fails_closed_on_budget_envelope() -> None:
    config = _read_config()
    from purposebench.utils import sha256_file

    config["workload_image_digest"] = (
        f"sha256:{sha256_file(ROOT / 'scripts/governed_openrouter_pair_bridge_v3.cjs')}"
    )
    config["budget"] = dict(config["budget"], absolute_authorized_eur=1000.0)
    with pytest.raises(ValueError, match="budget envelope"):
        validate_pair_validation_config(ROOT, config)


def test_load_cells_returns_exactly_b0_a_b0_b_p3_a_p3_b() -> None:
    config = _read_config()
    cells = load_cells(ROOT, config)
    assert [(c.condition, c.variant) for c in cells] == [
        ("B0", "A"),
        ("B0", "B"),
        ("P3", "A"),
        ("P3", "B"),
    ]


def test_b0_and_p3_partition_the_transmitted_manifest() -> None:
    config = _read_config()
    cells = load_cells(ROOT, config)
    for cell in cells:
        assert set(cell.approved_fields) | set(cell.prohibited_fields) == set(
            cell.selected_fields
        )
        assert cell.selected_fields == tuple(sorted(cell.selected_fields))
    b0 = cells[0]
    p3 = cells[2]
    assert set(b0.selected_fields) == set(b0.approved_fields) | set(
        b0.dataset_prohibited_fields
    )
    assert b0.prohibited_fields == b0.dataset_prohibited_fields
    assert p3.prohibited_fields == ()
    assert set(b0.selected_fields) == set(b0.records[0].keys())
    assert set(p3.selected_fields) == set(p3.records[0].keys())
    assert set(p3.selected_fields) == set(p3.approved_fields)
    assert p3.dataset_prohibited_fields == b0.dataset_prohibited_fields
    assert set(p3.dataset_prohibited_fields) == set(config["denied_fields"])


def test_ground_truth_is_identical_across_variants_and_conditions() -> None:
    config = _read_config()
    cells = load_cells(ROOT, config)
    assert cells[0].ground_truth == cells[1].ground_truth
    assert cells[2].ground_truth == cells[3].ground_truth
    assert cells[0].ground_truth in (PRIORITY_REVIEW, STANDARD_REVIEW)


def test_pair_bridge_payload_carries_the_classification() -> None:
    config = _read_config()
    cells = load_cells(ROOT, config)
    model = config["models"][0]
    payload = build_pair_bridge_payload(config, model, cells[0])
    assert payload["projectionClassification"] == {
        "approvedFields": list(cells[0].approved_fields),
        "prohibitedFields": list(cells[0].prohibited_fields),
    }
    assert payload["selectedFields"] == list(cells[0].selected_fields)
    assert set(payload["records"][0]) == set(payload["selectedFields"])


def test_release_policy_denies_prohibited_field_names_in_output() -> None:
    config = _read_config()
    policy = pair_release_policy(config)
    assert policy["decisionVocabulary"]["permittedValues"] == [
        PRIORITY_REVIEW,
        STANDARD_REVIEW,
    ]
    assert policy["prohibitedFieldNames"]["names"] == config["denied_fields"]
    assert set(policy["requiredValidators"]) == {
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
    }


def test_p3_cells_transmit_no_prohibited_values() -> None:
    config = _read_config()
    cells = load_cells(ROOT, config)
    for cell in cells[2:]:
        body = json.dumps(cell.records)
        for field in cell.dataset_prohibited_fields:
            assert field not in body
        for value in ("SYNTHETIC_ACTIVE_REVIEW", "SYNTHETIC_HIGH", "SYNTHETIC_VULNERABLE"):
            assert value not in body


def test_b0_cells_do_transmit_the_prohibited_values() -> None:
    config = _read_config()
    cells = load_cells(ROOT, config)
    for cell in cells[:2]:
        body = json.dumps(cell.records)
        assert any(field in body for field in cell.dataset_prohibited_fields)


def test_partition_mismatch_is_fail_closed() -> None:
    from purposebench.v3.transmission import classify_projection

    with pytest.raises(ProjectionClassificationError):
        classify_projection(["a"], ["a"], ["b"])


def test_first_pair_is_standard_review() -> None:
    config = _read_config()
    cells = load_cells(ROOT, config)
    assert cells[0].ground_truth == STANDARD_REVIEW
