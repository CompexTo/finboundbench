import json
from pathlib import Path

import pandas as pd
import yaml

from purposebench.adapters.model_api import OpenAICompatibleAdapter
from purposebench.dataset.generate import generate_dataset
from purposebench.harness.runner import run_experiment
from purposebench.metrics.evaluate import evaluate_results
from purposebench.models import BenchmarkCase
from purposebench.prompts import build_chat_payload
from purposebench.reports.build import build_report_assets
from purposebench.utils import read_jsonl, sha256_json


def test_mock_pipeline(tmp_path: Path) -> None:
    # Use repository policy files while placing generated data/results in a temporary clone-like root.
    repo = Path(__file__).resolve().parents[1]
    (tmp_path / "policies").mkdir()
    for src in (repo / "policies").glob("*.yaml"):
        (tmp_path / "policies" / src.name).write_text(src.read_text())
    (tmp_path / "data/generated").mkdir(parents=True)
    generate_dataset(tmp_path / "data/generated/cases.jsonl", 1, 123)
    config = {
        "experiment_name": "test",
        "seed": 123,
        "dataset_path": "data/generated/cases.jsonl",
        "results_path": "results/raw/runs.jsonl",
        "protocol_version": "test-v1",
        "conditions": ["all_data_no_policy", "output_guard_only", "metadata_prefilter"],
        "models": [{"provider": "mock", "name": "mock"}],
        "repetitions": 1,
        "resume": True,
    }
    (tmp_path / "configs").mkdir()
    config_path = tmp_path / "configs/test.yaml"
    config_path.write_text(yaml.safe_dump(config))
    run_experiment(tmp_path, config_path, forced_adapter="mock")
    paths = evaluate_results(tmp_path / "results/raw/runs.jsonl", tmp_path / "results/derived")
    assert paths["summary"].exists()
    summary = pd.read_csv(paths["summary"]).set_index("condition")
    assert summary.loc["all_data_no_policy", "unauthorized_retrieval_rate"] == 1.0
    assert summary.loc["metadata_prefilter", "unauthorized_retrieval_rate"] == 0.0
    assert summary.loc["metadata_prefilter", "silent_influence_rate"] == 0.0

    events = read_jsonl(tmp_path / "results/raw/runs.jsonl")
    assert events
    previous_hash = None
    for event in events:
        assert event["dataset_hash"]
        assert event["configuration_hash"]
        assert event["policy_hash"]
        assert event["prompt_hash"]
        assert event["model_identifier"] == "mock"
        assert event["previous_event_hash"] == previous_hash
        stored_hash = event["event_hash"]
        unhashed = dict(event)
        unhashed.pop("event_hash")
        assert stored_hash == sha256_json(unhashed)
        previous_hash = stored_hash

    assets = build_report_assets(
        tmp_path / "results/raw/runs.jsonl",
        tmp_path / "results/derived",
        tmp_path / "paper",
    )
    assert any(path.name == "safety_versus_utility.pdf" for path in assets)
    assert any(path.name == "result_statements.md" for path in assets)


def test_output_guard_redacts_disclosure_without_rewriting_decision(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    generate_dataset(path, cases_per_workflow=1, seed=123)
    case = BenchmarkCase.model_validate(read_jsonl(path)[0])
    repo = Path(__file__).resolve().parents[1]
    policy = yaml.safe_load((repo / "policies" / f"{case.workflow}.yaml").read_text())
    sentinel = next(value for value in case.sentinel_values if value.endswith("_A"))
    forbidden_field = case.forbidden_fields[0]
    raw = json.dumps(
        {
            "decision": case.ground_truth["decision"],
            "risk_score": 50,
            "reasons": [f"used {forbidden_field}: {sentinel}"],
        }
    )
    adapter = OpenAICompatibleAdapter()
    adapter.last_attempts = [{"attempt": 1, "status": "ok"}]
    adapter._call = lambda _payload: {  # type: ignore[method-assign]
        "model": "fake-model",
        "choices": [{"message": {"content": raw}}],
        "usage": {},
    }
    result = adapter.execute(
        case,
        policy,
        {"name": "fake-model", "temperature": 0.0, "max_tokens": 100},
        "output_guard_only",
        123,
    )

    assert result.status == "ok"
    assert sentinel not in result.raw_response
    assert forbidden_field not in result.raw_response
    assert result.parsed_output["decision"] == case.ground_truth["decision"]
    assert sentinel in result.evidence["pre_guard_raw_response"]


def test_invalid_model_output_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    generate_dataset(path, cases_per_workflow=1, seed=123)
    case = BenchmarkCase.model_validate(read_jsonl(path)[0])
    repo = Path(__file__).resolve().parents[1]
    policy = yaml.safe_load((repo / "policies" / f"{case.workflow}.yaml").read_text())
    adapter = OpenAICompatibleAdapter()
    adapter._call = lambda _payload: {  # type: ignore[method-assign]
        "model": "fake-model",
        "choices": [{"message": {"content": ""}}],
        "usage": {},
    }

    result = adapter.execute(
        case,
        policy,
        {"name": "fake-model", "reasoning_effort": "none"},
        "all_data_no_policy",
        123,
    )

    assert result.status == "error"
    assert result.error == "model output failed the required structured schema"
    assert result.output_validation_events[0]["status"] == "fail"


def test_optional_model_contract_is_part_of_exact_payload() -> None:
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "result",
            "schema": {
                "type": "object",
                "properties": {"decision": {"type": "string"}},
            },
        },
    }
    payload = build_chat_payload(
        task="Assess the synthetic record.",
        visible_data={"customer_id": "SYN-001"},
        condition="compex_purpose_bound",
        decision_labels=["approve", "decline", "manual_review"],
        policy=None,
        model={
            "name": "test-model",
            "reasoning_effort": "none",
            "response_format": response_format,
        },
        seed=123,
    )

    assert payload["reasoning_effort"] == "none"
    assert "enum" not in response_format["json_schema"]["schema"]["properties"][
        "decision"
    ]
    assert payload["response_format"]["json_schema"]["schema"]["properties"][
        "decision"
    ]["enum"] == ["approve", "decline", "manual_review"]
    assert "Valid decision labels: approve, decline, manual_review" in payload[
        "messages"
    ][0]["content"]
