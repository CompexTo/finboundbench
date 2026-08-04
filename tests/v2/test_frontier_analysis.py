from pathlib import Path

from purposebench.v2.frontier_analysis import analyze_frontier_pilots


def test_frontier_analysis_validates_pilots_and_retains_exclusion() -> None:
    root = Path.cwd()
    summaries, exclusions, manifest = analyze_frontier_pilots(
        root,
        Path("configs/v2/openrouter-frontier-matrix.json").resolve(),
    )
    assert len(summaries) == 5
    assert {row["status"] for row in summaries} == {"passed"}
    assert all(row["evidenceCompleteness"] == 1.0 for row in summaries)
    assert all(row["pairedInfluenceRate"] >= 0 for row in summaries)
    assert [row["modelId"] for row in exclusions] == ["anthropic/claude-opus-4.8"]
    assert exclusions[0]["pilotReservationCreated"] is False
    assert exclusions[0]["claudeFamilyFailedSmokeAttempts"] == 13
    assert manifest["committedCostEur"] < manifest["totalAuthorizedCostEur"]
