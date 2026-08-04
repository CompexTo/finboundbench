import json
from pathlib import Path

from purposebench.utils import sha256_json
from purposebench.v2.claude_closure import build_claude_closure_report


def test_claude_lane_closure_is_reproducible() -> None:
    root = Path.cwd()
    report = build_claude_closure_report(
        root,
        root / "configs/v2/openrouter-phase2.json",
    )
    assert report["status"] == "FORMALLY_CLOSED"
    assert report["gates"]["gate1"] == "FAILED_CLOSED_PROVIDER_ROUTING"
    assert report["gates"]["gate2"] == "NOT_RUN_GATE1_REQUIRED"
    assert report["failureInventory"]["priorFailureCount"] == 13
    assert report["failureInventory"]["totalDocumentedFailures"] == 14
    assert report["newAuthorization"]["providerCallsMade"] == 1
    assert report["newAuthorization"]["automaticRetries"] == 0
    assert report["budget"]["globalCommittedEur"] == 8.40239384
    assert report["budget"]["categoryCommittedEur"] == 0.5
    assert report["remainingExperimentPolicy"]["claudeEligible"] is False
    material = dict(report)
    observed = material.pop("closureHash")
    assert observed == sha256_json(material)

    stored_path = root / "results/v2/derived/openrouter-claude-closure.json"
    if stored_path.exists():
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        assert stored == report
