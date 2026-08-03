from pathlib import Path

import pytest

from purposebench.v2.experiments import ExperimentCondition
from purposebench.v2.inference_pilot import (
    _disclosure_findings,
    _validate_response,
    condition_prompts,
    load_paired_records,
    prepare_batch,
    response_schema,
)


def _dataset_path() -> Path:
    return Path("data/v2/generated/hmda-2024-dc-pairs.jsonl")


def test_batch_preparation_is_fair_and_full_conditions_retain_internal_fields() -> None:
    rows = load_paired_records(_dataset_path(), pair_limit=2)
    ordinary, ordinary_fields, denied = prepare_batch(
        rows, ExperimentCondition.ORDINARY_METADATA_PREFILTER
    )
    governed, governed_fields, governed_denied = prepare_batch(
        rows, ExperimentCondition.COMPEX_GOVERNED_LOCAL
    )
    full, full_fields, _ = prepare_batch(rows, ExperimentCondition.FULL_DATA_NO_POLICY)

    assert ordinary == governed
    assert ordinary_fields == governed_fields
    assert denied == governed_denied
    assert set(denied).isdisjoint(ordinary_fields)
    assert set(denied).issubset(full_fields)
    assert all(tuple(sorted(row)) == full_fields for row in full)


def test_schema_and_response_validation_bind_every_case_id() -> None:
    case_ids = ["case-a", "case-b"]
    schema = response_schema(case_ids)
    assert schema["properties"]["results"]["minItems"] == 2
    value = {
        "results": [
            {
                "case_id": case_id,
                "decision": "STANDARD_REVIEW",
                "risk_score": 20,
                "reasons": ["Approved field"],
            }
            for case_id in case_ids
        ]
    }
    assert len(_validate_response(value, case_ids)) == 2
    value["results"][1]["case_id"] = "case-a"
    with pytest.raises(ValueError, match="duplicated"):
        _validate_response(value, case_ids)


def test_prompt_only_is_explicit_and_disclosure_scan_records_hashes_only() -> None:
    rows = load_paired_records(_dataset_path(), pair_limit=1)
    denied = tuple(rows[0]["prohibited_internal_fields"])
    prompts = condition_prompts(ExperimentCondition.PROMPT_ONLY_RESTRICTION, denied)
    assert all(field in prompts["system"] for field in denied)
    secret_value = str(rows[0]["fields"][denied[0]])
    findings = _disclosure_findings(f"leaked {denied[0]} {secret_value}", rows)
    assert findings
    assert secret_value not in str(findings)
