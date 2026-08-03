from pathlib import Path

import pytest

from purposebench.v2.experiments import ExperimentCondition
from purposebench.v2.inference_pilot import (
    MODEL_RETRY_POLICY,
    MODEL_TIMEOUTS_MS,
    DirectOllamaInvoker,
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
            }
            for case_id in case_ids
        ]
    }
    assert len(_validate_response(value, case_ids)) == 2
    value["results"][1]["case_id"] = "case-a"
    with pytest.raises(ValueError, match="duplicated"):
        _validate_response(value, case_ids)


def test_large_batch_uses_compact_order_bound_response() -> None:
    case_ids = [f"case-{index:02d}" for index in range(40)]
    schema = response_schema(case_ids)
    assert set(schema["properties"]) == {"decisions", "risk_scores"}
    value = {
        "decisions": ["STANDARD_REVIEW"] * 20 + ["MANUAL_REVIEW"] * 20,
        "risk_scores": list(range(40)),
    }
    normalized = _validate_response(value, case_ids)
    assert [row["case_id"] for row in normalized] == case_ids
    assert normalized[-1] == {
        "case_id": "case-39",
        "decision": "MANUAL_REVIEW",
        "risk_score": 39,
    }
    value["risk_scores"] = value["risk_scores"][:-1]
    with pytest.raises(ValueError, match="array counts"):
        _validate_response(value, case_ids)


def test_compact_prompt_binds_output_indexes_to_input_order() -> None:
    prompt = condition_prompts(
        ExperimentCondition.COMPEX_GOVERNED_LOCAL,
        ("denied",),
        compact_response=True,
    )["task"]
    assert "Array index i" in prompt
    assert "input record index i" in prompt
    assert "do not return case IDs" in prompt


def test_direct_and_governed_paths_share_bounded_model_deadlines() -> None:
    invoker = DirectOllamaInvoker()
    try:
        assert invoker.client.timeout.read == max(MODEL_TIMEOUTS_MS.values()) / 1_000
    finally:
        invoker.close()
    assert MODEL_TIMEOUTS_MS == {
        "qwen3-4b": 1_200_000,
        "gemma4-31b": 2_700_000,
    }
    assert MODEL_RETRY_POLICY == {
        "maxAttempts": 1,
        "initialBackoffMs": 0,
        "maximumBackoffMs": 0,
        "retryableStatusCodes": [],
    }


def test_prompt_only_is_explicit_and_disclosure_scan_records_hashes_only() -> None:
    rows = load_paired_records(_dataset_path(), pair_limit=1)
    denied = tuple(rows[0]["prohibited_internal_fields"])
    prompts = condition_prompts(ExperimentCondition.PROMPT_ONLY_RESTRICTION, denied)
    assert all(field in prompts["system"] for field in denied)
    secret_value = str(rows[0]["fields"][denied[0]])
    findings = _disclosure_findings(f"leaked {denied[0]} {secret_value}", rows)
    assert findings
    assert secret_value not in str(findings)


def test_failed_batches_are_not_treated_as_completed_resume_keys(tmp_path: Path) -> None:
    # The raw stream may retain failed attempts, but a later passing record for
    # the same dedupe key remains necessary for protocol completion.
    from purposebench.utils import append_jsonl, read_jsonl

    path = tmp_path / "attempts.jsonl"
    append_jsonl(path, {"dedupeKey": "same", "status": "failed"})
    completed = {
        row["dedupeKey"] for row in read_jsonl(path) if row.get("status") == "passed"
    }
    assert completed == set()
    append_jsonl(path, {"dedupeKey": "same", "status": "passed"})
    completed = {
        row["dedupeKey"] for row in read_jsonl(path) if row.get("status") == "passed"
    }
    assert completed == {"same"}
