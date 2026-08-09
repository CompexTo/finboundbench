"""Anti-gaming suite tests: the seven degenerate strategies must show their
expected signatures on the development split. Also verifies response schema
conformance and that the oracle is the dev-only upper bound.

Run from the repository root: python -m pytest competition/evaluator/test_anti_gaming.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from competition.baselines import BASELINES
from competition.evaluator.harness import PythonSubmission, run_submission
from competition.evaluator.metrics import (
    CONSTRAINT_AVAILABILITY,
    CONSTRAINT_MARGIN,
    QUALITY_GATE_AUR,
    compute_metrics,
)
from competition.evaluator.payloads import CONDITIONS, load_jsonl, load_manifest, render_split

REPO_ROOT = Path(__file__).resolve().parents[2]
PAIRS_PATH = REPO_ROOT / "data/v4/v4_calibr/pairs.jsonl"
MANIFEST_PATH = REPO_ROOT / "data/v4/v4_signal_manifest.json"


@pytest.fixture(scope="module")
def data():
    pairs = load_jsonl(str(PAIRS_PATH))
    signals = load_manifest(str(MANIFEST_PATH))["signals"]
    requests = render_split(pairs, signals, CONDITIONS)
    return pairs, requests


def score(name: str, requests, pairs):
    submission = PythonSubmission(BASELINES[name], name)
    decisions = run_submission(submission, requests, inject_labels_for="oracle")
    return compute_metrics(pairs, decisions)


def test_all_baselines_are_schema_conformant(data):
    requests = data[1]
    for name in BASELINES:
        submission = PythonSubmission(BASELINES[name], name)
        decisions = run_submission(submission, requests, inject_labels_for="oracle")
        for entry in decisions.values():
            response = entry["response"]
            assert isinstance(response, dict)
            assert set(response.keys()) <= {"action", "cost_usd", "evidence", "error"}
            action = response.get("action")
            assert action is None or isinstance(action, str)


def test_always_refuse_passes_constraint_fails_quality(data):
    pairs, requests = data
    m = score("always-refuse", requests, pairs)
    assert m["constraint_ok"] is True
    assert m["net_ui"] == 0.0
    assert m["policy_violations"] == 0
    assert m["availability"] >= CONSTRAINT_AVAILABILITY
    assert m["quality_ok"] is False
    assert m["aur"] is None or m["aur"] < QUALITY_GATE_AUR


def test_always_same_passes_constraint_fails_quality(data):
    pairs, requests = data
    m = score("always-same", requests, pairs)
    assert m["constraint_ok"] is True
    assert m["net_ui"] == 0.0
    assert m["quality_ok"] is False


def test_always_use_full_maximizes_utility_but_leaks(data):
    pairs, requests = data
    m = score("always-use-full", requests, pairs)
    assert m["quality_ok"] is True
    assert m["aur"] is not None and m["aur"] >= QUALITY_GATE_AUR
    assert m["constraint_ok"] is False
    assert m["net_ui"] is not None and m["net_ui"] > CONSTRAINT_MARGIN
    assert m["uir"]["P0"] == pytest.approx(1.0)
    assert m["uir"]["P3"] == pytest.approx(1.0)


def test_ignore_confidential_shows_no_influence_and_no_utility(data):
    pairs, requests = data
    m = score("ignore-confidential", requests, pairs)
    assert m["uir"]["P0"] == 0.0
    assert m["uir"]["P2"] == 0.0
    assert m["uir"]["P3"] == 0.0
    assert m["nd_floor"] == 0.0
    assert m["quality_ok"] is False
    assert m["bacc"]["A3"] == m["bacc"]["A0"]


def test_random_has_positive_floor_and_no_utility(data):
    pairs, requests = data
    m = score("random", requests, pairs)
    assert m["nd_floor"] is not None and m["nd_floor"] > 0.3
    assert m["bacc"]["A3"] is not None and 0.45 < m["bacc"]["A3"] < 0.55
    assert m["quality_ok"] is False


def test_purpose_agnostic_shows_no_purpose_distinction(data):
    pairs, requests = data
    m = score("purpose-agnostic", requests, pairs)
    assert m["uir"]["P0"] == m["uir"]["P3"]
    assert m["uir"]["P3"] == pytest.approx(1.0)


def test_oracle_is_upper_bound_and_dev_only(data):
    pairs, requests = data
    m = score("oracle", requests, pairs)
    assert m["bacc"]["A3"] == pytest.approx(1.0)
    assert m["nd_floor"] == 0.0
    assert m["constraint_ok"] is True
    assert m["uir"]["P0"] == 0.0
    assert m["aur"] is None
    for name in BASELINES:
        if name == "oracle":
            continue
        other = score(name, requests, pairs)
        assert m["bacc"]["A3"] >= (other["bacc"]["A3"] or 0.0)


def test_sample_submission_satisfies_constraint(data):
    pairs, requests = data
    from competition.sample_submission.decide import decide as sample_decide

    submission = PythonSubmission(sample_decide, "sample-submission")
    decisions = run_submission(submission, requests, inject_labels_for="oracle")
    m = compute_metrics(pairs, decisions)
    assert m["constraint_ok"] is True
    assert m["policy_violations"] == 0
    assert m["availability"] >= CONSTRAINT_AVAILABILITY
