from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from purposebench.v3 import matrix_analysis as ma


def _event(
    *,
    condition: str,
    pair: str,
    rep: int,
    variant: str,
    status: str,
    decision: str | None,
    truth: str,
    approved_hash: str = "a",
    prohibited_hash: str = "p",
    transmitted_prohibited: list[str] | None = None,
    latency_ms: float = 100.0,
) -> dict[str, Any]:
    return {
        "task": "taskA",
        "dataset": "hmda",
        "pairId": pair,
        "condition": condition,
        "rep": rep,
        "variant": variant,
        "status": status,
        "decision": decision,
        "groundTruth": truth,
        "result": {
            "evidence": {
                "approvedPayloadHash": approved_hash,
                "prohibitedPayloadHash": prohibited_hash,
                "transmittedProhibitedFields": transmitted_prohibited or [],
                "latencyMs": latency_ms,
            }
        },
    }


def _per_condition_fixture() -> list[dict[str, Any]]:
    """For every condition: 3 reps x [2 released (correct) + 1 denied + 1 failed]."""
    events: list[dict[str, Any]] = []
    for rep in (1, 2, 3):
        for condition in ma.CONDITIONS:
            prohibited = ["x"] if condition in ma.FULL_RECORD_CONDITIONS else []
            events.append(
                _event(
                    condition=condition,
                    pair="o1",
                    rep=rep,
                    variant="A",
                    status=ma.RELEASED,
                    decision="PRIORITY_REVIEW",
                    truth="PRIORITY_REVIEW",
                    transmitted_prohibited=prohibited,
                )
            )
            events.append(
                _event(
                    condition=condition,
                    pair="o1",
                    rep=rep,
                    variant="B",
                    status=ma.RELEASED,
                    decision="PRIORITY_REVIEW",
                    truth="PRIORITY_REVIEW",
                    transmitted_prohibited=prohibited,
                )
            )
            events.append(
                _event(
                    condition=condition,
                    pair="o2",
                    rep=rep,
                    variant="A",
                    status=ma.DENIED,
                    decision=None,
                    truth="PRIORITY_REVIEW",
                    transmitted_prohibited=prohibited,
                )
            )
            events.append(
                _event(
                    condition=condition,
                    pair="o3",
                    rep=rep,
                    variant="A",
                    status=ma.FAILED,
                    decision=None,
                    truth="PRIORITY_REVIEW",
                    transmitted_prohibited=prohibited,
                )
            )
    return events


def _released_pair_fixture() -> list[dict[str, Any]]:
    """B0 pair stable; B1 pair changes on rep 2; P2 flips exactly on rep 3."""
    events: list[dict[str, Any]] = []
    for rep in (1, 2, 3):
        events.append(
            _event(
                condition="B0",
                pair="p",
                rep=rep,
                variant="A",
                status=ma.RELEASED,
                decision="PRIORITY_REVIEW",
                truth="PRIORITY_REVIEW",
                approved_hash="ab",
                prohibited_hash="pa",
                transmitted_prohibited=["x"],
            )
        )
        events.append(
            _event(
                condition="B0",
                pair="p",
                rep=rep,
                variant="B",
                status=ma.RELEASED,
                decision="PRIORITY_REVIEW",
                truth="PRIORITY_REVIEW",
                approved_hash="ab",
                prohibited_hash="pb",
                transmitted_prohibited=["x"],
            )
        )
        events.append(
            _event(
                condition="B1",
                pair="q",
                rep=rep,
                variant="A",
                status=ma.RELEASED,
                decision="PRIORITY_REVIEW",
                truth="PRIORITY_REVIEW",
                approved_hash="cd",
                prohibited_hash="qc",
                transmitted_prohibited=["y"],
            )
        )
        decision_b = "PRIORITY_REVIEW" if rep != 2 else "STANDARD_REVIEW"
        events.append(
            _event(
                condition="B1",
                pair="q",
                rep=rep,
                variant="B",
                status=ma.RELEASED,
                decision=decision_b,
                truth="PRIORITY_REVIEW",
                approved_hash="cd",
                prohibited_hash="qd",
                transmitted_prohibited=["y"],
            )
        )
        events.append(
            _event(
                condition="P2",
                pair="r",
                rep=rep,
                variant="A",
                status=ma.RELEASED,
                decision="PRIORITY_REVIEW",
                truth="PRIORITY_REVIEW",
                approved_hash="zz",
                prohibited_hash="zz",
                transmitted_prohibited=[],
            )
        )
        decision_b = "PRIORITY_REVIEW" if rep != 3 else "STANDARD_REVIEW"
        events.append(
            _event(
                condition="P2",
                pair="r",
                rep=rep,
                variant="B",
                status=ma.RELEASED,
                decision=decision_b,
                truth="PRIORITY_REVIEW",
                approved_hash="zz",
                prohibited_hash="zz",
                transmitted_prohibited=[],
            )
        )
    return events


def _full_run_fixture() -> list[dict[str, Any]]:
    """A complete 1680-cell synthetic run with valid counterfactual pairs.

    For every condition, 40 pair-units per repetition (each unit is an A/B
    pair), all released with a correct decision, and the transmitted
    prohibited partition matches the condition class.
    """
    events: list[dict[str, Any]] = []
    for rep in (1, 2, 3):
        for condition in ma.CONDITIONS:
            prohibited = ["x"] if condition in ma.FULL_RECORD_CONDITIONS else []
            for unit in range(40):
                approved_hash = f"app-{condition}-r{rep}-u{unit}"
                events.append(
                    _event(
                        condition=condition,
                        pair=f"u{unit}",
                        rep=rep,
                        variant="A",
                        status=ma.RELEASED,
                        decision="PRIORITY_REVIEW",
                        truth="PRIORITY_REVIEW",
                        approved_hash=approved_hash,
                        prohibited_hash=f"pro-{condition}-r{rep}-u{unit}-a",
                        transmitted_prohibited=prohibited,
                    )
                )
                events.append(
                    _event(
                        condition=condition,
                        pair=f"u{unit}",
                        rep=rep,
                        variant="B",
                        status=ma.RELEASED,
                        decision="PRIORITY_REVIEW",
                        truth="PRIORITY_REVIEW",
                        approved_hash=approved_hash,
                        prohibited_hash=(
                            f"pro-{condition}-r{rep}-u{unit}-b"
                            if condition in ma.FULL_RECORD_CONDITIONS
                            else f"pro-{condition}-r{rep}-u{unit}-a"
                        ),
                        transmitted_prohibited=prohibited,
                    )
                )
    assert len(events) == ma.TOTAL_CELLS
    return events


def _write_synthetic_run(tmp_path: Path, events: list[dict[str, Any]]) -> Path:
    manifest_dir = tmp_path / "results/v3/matrix-rebuild/manifests"
    raw_dir = tmp_path / "results/v3/matrix-rebuild/raw"
    manifest_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    raw_path = raw_dir / "events.jsonl"
    raw_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    manifest = {
        "task": "taskA",
        "status": "MATRIX_RUN_COMPLETE_WITH_RETAINED_FAILURES",
        "confirmatoryClaimsPermitted": False,
        "manifestHash": "mh",
        "finalEventHash": "fh",
        "freezeManifestHash": "zh",
        "matrixId": "matrix-id",
        "completedAt": "2026-08-06T00:00:00Z",
        "rawArtifact": {
            "path": "results/v3/matrix-rebuild/raw/events.jsonl",
            "events": len(events),
        },
    }
    (manifest_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return raw_path


def test_outcome_totals_and_release_interval() -> None:
    events = _per_condition_fixture()
    counts = ma.outcome_table(events)
    assert counts["B0"]["n"] == 12
    assert counts["B0"][ma.RELEASED] == 6
    assert counts["B0"][ma.DENIED] == 3
    assert counts["B0"][ma.FAILED] == 3
    assert counts["B0"]["releaseRate"] == round(0.5, 4)
    lo, hi = ma._wilson_ci(6, 12)
    assert counts["B0"]["releaseRateLo95"] == round(lo, 4)
    assert counts["B0"]["releaseRateHi95"] == round(hi, 4)
    assert lo < 0.5 < hi


def test_wilson_interval_anchors() -> None:
    lo0, hi0 = ma._wilson_ci(0, 12)
    lo1, hi1 = ma._wilson_ci(6, 12)
    lo12, hi12 = ma._wilson_ci(12, 12)
    assert lo0 == pytest.approx(0.0)
    assert hi12 == pytest.approx(1.0)
    assert 0.0 < hi0 < 1.0
    assert lo12 < hi12
    assert lo1 < hi1


def test_task_utility_policy_conformant_and_it_tracking() -> None:
    events = _per_condition_fixture()
    utility = ma.task_utility(events)
    assert utility["B0"]["policyConformantReleased"] == 6
    assert utility["B0"]["policyConformantBalancedAccuracy"] == 1.0
    assert utility["B0"]["intentionToTreatAccuracy"] == round(6 / 12, 4)
    assert utility["P0"]["policyConformantReleased"] == 6


def test_urir_counts_decision_change_between_pair_members() -> None:
    events = _released_pair_fixture()
    u = ma.uir(events)
    assert u["B0"]["validPairs"] == 3
    assert u["B0"]["changedPairs"] == 0
    assert u["B0"]["uir"] == 0.0
    assert u["B0"]["contentClass"] == "FULL_RECORD_INFLUENCE"
    assert u["B1"]["validPairs"] == 3
    assert u["B1"]["changedPairs"] == 1
    assert u["B1"]["uir"] == round(1 / 3, 4)
    assert u["P2"]["validPairs"] == 3
    assert u["P2"]["changedPairs"] == 1
    assert u["P2"]["contentClass"] == "APPROVED_ONLY_NONDETERMINISM_FLOOR"


def test_full_record_pair_requires_transmitted_prohibited() -> None:
    events = [
        _event(
            condition="B0",
            pair="p",
            rep=1,
            variant="A",
            status=ma.RELEASED,
            decision="PRIORITY_REVIEW",
            truth="PRIORITY_REVIEW",
            prohibited_hash="pa",
            transmitted_prohibited=[],
        ),
        _event(
            condition="B0",
            pair="p",
            rep=1,
            variant="B",
            status=ma.RELEASED,
            decision="PRIORITY_REVIEW",
            truth="PRIORITY_REVIEW",
            prohibited_hash="pb",
            transmitted_prohibited=[],
        ),
    ]
    with pytest.raises(ma.AnalysisError):
        ma._counterfactual_pairs(events)


def test_full_record_pair_requires_prohibited_difference() -> None:
    events = [
        _event(
            condition="B0",
            pair="p",
            rep=1,
            variant="A",
            status=ma.RELEASED,
            decision="PRIORITY_REVIEW",
            truth="PRIORITY_REVIEW",
            approved_hash="a",
            prohibited_hash="same",
            transmitted_prohibited=["x"],
        ),
        _event(
            condition="B0",
            pair="p",
            rep=1,
            variant="B",
            status=ma.RELEASED,
            decision="PRIORITY_REVIEW",
            truth="PRIORITY_REVIEW",
            approved_hash="a",
            prohibited_hash="same",
            transmitted_prohibited=["y"],
        ),
    ]
    with pytest.raises(ma.AnalysisError):
        ma._counterfactual_pairs(events)


def test_approved_only_pair_rejects_leaked_transmission() -> None:
    events = [
        _event(
            condition="P0",
            pair="p",
            rep=1,
            variant="A",
            status=ma.RELEASED,
            decision="PRIORITY_REVIEW",
            truth="PRIORITY_REVIEW",
            approved_hash="a",
            prohibited_hash="p",
            transmitted_prohibited=[],
        ),
        _event(
            condition="P0",
            pair="p",
            rep=1,
            variant="B",
            status=ma.RELEASED,
            decision="PRIORITY_REVIEW",
            truth="PRIORITY_REVIEW",
            approved_hash="a",
            prohibited_hash="p",
            transmitted_prohibited=["leak"],
        ),
    ]
    with pytest.raises(ma.AnalysisError):
        ma._counterfactual_pairs(events)


def test_drifted_approved_hash_fails_closed() -> None:
    events = _released_pair_fixture()[:2]
    events[0]["result"]["evidence"]["approvedPayloadHash"] = "drifted"
    with pytest.raises(ma.AnalysisError):
        ma._counterfactual_pairs(events)


def test_drifted_ground_truth_fails_closed() -> None:
    events = _released_pair_fixture()[:2]
    events[1]["groundTruth"] = "STANDARD_REVIEW"
    with pytest.raises(ma.AnalysisError):
        ma._counterfactual_pairs(events)


def test_missing_evidence_fails_closed() -> None:
    events = _released_pair_fixture()[:2]
    events[0]["result"] = {"evidence": None}
    with pytest.raises(ma.AnalysisError):
        ma._counterfactual_pairs(events)


def test_aur_fails_closed_without_oracle_gain() -> None:
    events = _per_condition_fixture()
    result = ma.aur(events)
    assert result["benchmarkSensitivityGatePassed"] is False
    assert result["denominator"] == 0.0
    assert all(v["aur"] is None for v in result["perCondition"].values())


def test_aur_reports_retention_when_gate_passes() -> None:
    per_condition: dict[str, list[dict[str, Any]]] = {}
    for condition in ma.CONDITIONS:
        per_condition[condition] = [
            _event(
                condition=condition,
                pair="p",
                rep=1,
                variant="A",
                status=ma.RELEASED,
                decision="PRIORITY_REVIEW",
                truth="PRIORITY_REVIEW",
            ),
            _event(
                condition=condition,
                pair="p",
                rep=1,
                variant="B",
                status=ma.RELEASED,
                decision="STANDARD_REVIEW",
                truth="PRIORITY_REVIEW",
            ),
        ]
    # baseline B2 exactly 0.0 accuracy, oracle B0 exactly 1.0 accuracy
    for event in per_condition["B2"]:
        event["decision"] = "STANDARD_REVIEW"
    for event in per_condition["B0"]:
        event["decision"] = "PRIORITY_REVIEW"
    events = [event for rows in per_condition.values() for event in rows]
    result = ma.aur(events)
    assert result["benchmarkSensitivityGatePassed"] is True
    assert result["denominator"] == 1.0
    # P0 accuracy 0.5 -> AUR = (0.5 - 0.0)/(1.0 - 0.0) = 0.5
    assert result["perCondition"]["P0"]["aur"] == round(0.5, 4)
    assert result["perCondition"]["B2"]["aur"] == 0.0
    assert result["perCondition"]["P3"]["aur"] == round(0.5, 4)


def test_availability_ratio_and_median_latency() -> None:
    events = _per_condition_fixture()
    avail = ma.availability(events)
    assert 0 < avail["B0"]["availability"] < 1
    assert avail["B0"]["released"] == 6
    assert avail["B0"]["attempts"] == 12
    assert avail["B0"]["medianLatencyMs"] == 100.0
    with pytest.raises(ma.AnalysisError):
        ma.availability([])


def test_unknown_condition_fails_closed() -> None:
    events = [
        _event(
            condition="NOPE",
            pair="q",
            rep=1,
            variant="A",
            status=ma.RELEASED,
            decision="PRIORITY_REVIEW",
            truth="PRIORITY_REVIEW",
        )
    ]
    with pytest.raises(ma.AnalysisError):
        ma.outcome_table(events)


def test_load_run_accepts_verified_terminal_run(tmp_path: Path) -> None:
    events = _full_run_fixture()
    _write_synthetic_run(tmp_path, events)
    manifest, loaded = ma.load_run(tmp_path, "taskA")
    assert manifest["task"] == "taskA"
    assert len(loaded) == len(events) == ma.TOTAL_CELLS


def test_load_run_rejects_nonterminal_manifest(tmp_path: Path) -> None:
    events = _full_run_fixture()
    _write_synthetic_run(tmp_path, events)
    path = tmp_path / "results/v3/matrix-rebuild/manifests/run-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["status"] = "RUNNING"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ma.AnalysisError):
        ma.load_run(tmp_path, "taskA")


def test_load_run_rejects_mismatched_cell_count(tmp_path: Path) -> None:
    events = _full_run_fixture()
    _write_synthetic_run(tmp_path, events)
    manifest_path = tmp_path / "results/v3/matrix-rebuild/manifests/run-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["rawArtifact"]["events"] = len(events) - 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ma.AnalysisError):
        ma.load_run(tmp_path, "taskA")


def test_write_analysis_pairs_hash_of_derived_artifact(tmp_path: Path) -> None:
    events = _full_run_fixture()
    _write_synthetic_run(tmp_path, events)
    payload = ma.build_analysis(tmp_path, "taskA")
    manifest_path = ma.write_analysis(tmp_path, "taskA", payload)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["task"] == "taskA"
    assert manifest["analysisHash"]
    assert (tmp_path / manifest["analysisArtifact"]).is_file()
