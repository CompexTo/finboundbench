import json
from pathlib import Path

from purposebench.utils import sha256_json
from purposebench.v2.frontier_replication import build_frontier_replication_report


def test_frontier_replication_validates_three_planned_attempts() -> None:
    root = Path.cwd()
    report = build_frontier_replication_report(
        root,
        root / "configs/v2/openrouter-frontier-matrix.json",
    )
    eligible = [
        model for model in report["models"] if model["status"] != "INELIGIBLE_SMOKE_GATE"
    ]
    excluded = [
        model for model in report["models"] if model["status"] == "INELIGIBLE_SMOKE_GATE"
    ]
    assert len(eligible) == 5
    assert len(excluded) == 1
    assert report["plannedAttempts"] == 15
    assert report["successfulAttempts"] == 13
    assert report["failedClosedAttempts"] == 2
    assert report["pairedPurpose"] == {
        "successfulPairObservations": 260,
        "influencedPairObservations": 8,
        "successfulAttemptsWithInfluence": 1,
        "successfulAttemptsWithoutInfluence": 12,
    }
    assert sum(model["failedAttempts"] for model in eligible) == 2
    assert all(
        model["stabilityAcrossSuccessfulAttempts"]["comparedAttempts"] >= 2
        for model in eligible
    )
    assert report["budget"]["committedEur"] == 7.90239384
    assert report["budget"]["remainingEur"] == 2.09760616
    by_model = {model["modelId"]: model for model in eligible}
    assert by_model["deepseek/deepseek-v4-pro"]["stabilityAcrossSuccessfulAttempts"][
        "decisionExactAgreementRate"
    ] == 1.0
    assert by_model["openai/gpt-5.6-luna"]["attempts"][1]["pairMetrics"][
        "pairedInfluenceRate"
    ] == 0.4
    material = dict(report)
    observed = material.pop("reportHash")
    assert observed == sha256_json(material)

    stored_path = root / "results/v2/derived/openrouter-frontier-replication.json"
    if stored_path.exists():
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        assert stored == report
