import json
from pathlib import Path

from purposebench.utils import sha256_json
from purposebench.v2.position_analysis import build_position_report


def test_position_report_reproduces_governed_diagnostic() -> None:
    root = Path.cwd()
    report = build_position_report(root)
    assert report["status"] == "COMPLETE_WITH_MODEL_FAILURE"
    by_model = {model["modelId"]: model for model in report["models"]}
    gpt = by_model["openai/gpt-5.6-luna"]
    deepseek = by_model["deepseek/deepseek-v4-pro"]
    assert gpt["invocationCount"] == 11
    assert len(gpt["layouts"]) == 9
    assert gpt["eligibleForReducedGovernedMatrix"] is True
    assert deepseek["status"] == "FAILED_CLOSED"
    assert deepseek["providerCalls"] == 1
    assert deepseek["eligibleForReducedGovernedMatrix"] is False
    assert report["budget"]["categoryCommittedEur"] == 0.099562
    assert report["budget"]["globalCommittedEur"] == 8.50195584
    material = dict(report)
    observed = material.pop("reportHash")
    assert observed == sha256_json(material)

    stored_path = root / "results/v2/derived/openrouter-position-diagnostic.json"
    if stored_path.exists():
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        assert stored == report
