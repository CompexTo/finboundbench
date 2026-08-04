import json
from pathlib import Path

from purposebench.utils import sha256_json
from purposebench.v2.frontier_report import (
    build_frontier_comparison,
    finalize_frontier_comparison,
)


def test_frontier_report_compares_only_validated_pilots() -> None:
    root = Path.cwd()
    report = finalize_frontier_comparison(
        build_frontier_comparison(
            root,
            root / "configs/v2/openrouter-frontier-matrix.json",
        )
    )
    passed = [model for model in report["models"] if model["status"] == "PASSED"]
    ineligible = [
        model for model in report["models"] if model["status"] == "INELIGIBLE_SMOKE_GATE"
    ]
    assert len(passed) == 5
    assert len(ineligible) == 1
    assert "claude" in ineligible[0]["modelId"]
    assert all(model["paired"]["decisionAgreementRate"] == 1.0 for model in passed)
    assert all(model["paired"]["riskScoreExactAgreementRate"] == 1.0 for model in passed)
    assert len(report["crossModel"]["pairwise"]) == 10
    assert report["budget"]["committedEur"] == 7.31403062
    material = dict(report)
    observed = material.pop("comparisonHash")
    assert observed == sha256_json(material)
    stored = json.loads(
        (root / "results/v2/derived/openrouter-frontier-pilot-comparison.json").read_text(
            encoding="utf-8"
        )
    )
    assert stored == report
