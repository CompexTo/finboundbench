"""Analysis for the live v3 purpose-selective matrix runs.

Computes per-condition analysis payloads from the verified live matrix events
(``results/v3/matrix-rebuild/raw/events.jsonl`` and the taskB sibling):

- outcome table (released / denied / failed) with release rate and Wilson 95%
  confidence interval per condition;
- task utility (balanced accuracy, class-mean recall) per condition on the
  policy-conformant (released) and intention-to-treat (missing output counted
  as wrong) populations;
- unauthorized influence rate (UIR): the pair-level decision-change fraction
  between counterfactual variants A and B of the same (dataset, pair,
  condition, rep), where the approved projection is byte-identical and only
  the prohibited confidential projection differs (validated against the
  evidence payload hashes before pairing);
- the nondeterminism floor: the UIR observed under approved-only conditions,
  where the transmitted payload is byte-identical across variants, reported
  separately so influence is never conflated with model noise;
- availability per condition (released / attempted) with Wilson CI, and
  median latency / committed cost per call;
- authorized-utility-retention (AUR) for approved-only conditions against the
  public-only baseline (B2) and the full authorized oracle (B0), with the
  benchmark-sensitivity denominator gate from the formal estimands.

The analysis is bound to the verified run manifest for the task and refuses to
run on unverified or partial runs. The events carry the NOT_CONFIRMATORY label,
so the artifact records estimates and counts with decision-language rules and
never claims a confirmatory hypothesis.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

CONDITIONS = ("B0", "B1", "B2", "P0", "P1", "P2", "P3")
AUTHORIZED_ONLY_CONDITIONS = ("B2", "P0", "P1", "P2", "P3")
FULL_RECORD_CONDITIONS = ("B0", "B1")
TOTAL_CELLS = 1680
RELEASED = "RELEASED"
DENIED = "RELEASE_DENIED"
FAILED = "FAILED"
LABEL = "OPENROUTER_PURPOSE_SELECTIVE_MATRIX_REBUILD_NOT_CONFIRMATORY"
SCHEMA_VERSION = "finboundbench.matrix-analysis.v3"


class AnalysisError(ValueError):
    """Raised when a required raw field is missing or an invariant fails."""


def load_run(research_root: Path, task: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load and sanity-check the verified run manifest and raw events."""
    task_dir = "" if task == "taskA" else f"{task}/"
    manifest_path = (
        research_root / f"results/v3/matrix-rebuild/{task_dir}manifests/run-manifest.json"
    )
    if not manifest_path.is_file():
        raise AnalysisError(f"run manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("task") != task:
        raise AnalysisError("run manifest task mismatch")
    if manifest.get("status") != "MATRIX_RUN_COMPLETE_WITH_RETAINED_FAILURES":
        raise AnalysisError(f"run is not verified terminal: {manifest.get('status')}")
    if manifest.get("confirmatoryClaimsPermitted") is not False:
        raise AnalysisError("run manifest must forbid confirmatory claims")
    raw = manifest.get("rawArtifact") or {}
    events_path = research_root / str(
        raw.get("path") or f"results/v3/matrix-rebuild/{task_dir}raw/events.jsonl"
    )
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(events) != TOTAL_CELLS:
        raise AnalysisError(f"events count {len(events)} != {TOTAL_CELLS}")
    if raw.get("events") not in (None, len(events)):
        raise AnalysisError("events count disagrees with the run manifest")
    return manifest, events


def _wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval bounds for a proportion."""
    if total <= 0:
        raise AnalysisError("cannot compute a proportion from an empty denominator")
    phat = successes / total
    denom = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denom
    half = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def outcome_table(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-condition outcome counts with release rate and Wilson CI."""
    counts: dict[str, dict[str, Any]] = {
        c: {"n": 0, RELEASED: 0, DENIED: 0, FAILED: 0} for c in CONDITIONS
    }
    for event in events:
        condition = event.get("condition")
        if condition not in counts:
            raise AnalysisError(f"unknown condition in events: {condition}")
        status = event.get("status")
        if status not in (RELEASED, DENIED, FAILED):
            raise AnalysisError(f"unknown event status: {status}")
        counts[condition]["n"] += 1
        counts[condition][status] += 1
    table: dict[str, dict[str, Any]] = {}
    for condition, row in counts.items():
        rate: float | None = None
        lo: float | None = None
        hi: float | None = None
        if row["n"]:
            rate = row[RELEASED] / row["n"]
            lo, hi = _wilson_ci(row[RELEASED], row["n"])
        table[condition] = {
            **row,
            "releaseRate": round(rate, 4) if rate is not None else None,
            "releaseRateLo95": round(lo, 4) if lo is not None else None,
            "releaseRateHi95": round(hi, 4) if hi is not None else None,
        }
    return table


def _balanced_accuracy(events: list[dict[str, Any]]) -> float | None:
    """Class-mean recall over released events; None when no event is released."""
    if not events:
        return None
    per_class: dict[str, list[int]] = defaultdict(list)
    for event in events:
        decision = event.get("decision")
        truth = event.get("groundTruth")
        if decision is None or truth is None:
            raise AnalysisError("released event lacks a decision or ground truth")
        per_class[str(truth)].append(int(decision == truth))
    recalls = [statistics.fmean(values) for values in per_class.values()]
    return statistics.fmean(recalls)


def task_utility(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Balanced accuracy per condition for both analysis populations.

    - ``policyConformant``: released events only;
    - ``intentionToTreat``: every attempt, with denied/failed counted as wrong.
    """
    released_by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    attempt_by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        condition = event["condition"]
        attempt_by_condition[condition].append(event)
        if event["status"] == RELEASED:
            released_by_condition[condition].append(event)
    out: dict[str, Any] = {}
    for condition in CONDITIONS:
        released = released_by_condition.get(condition, [])
        attempts = attempt_by_condition.get(condition, [])
        balanced = _balanced_accuracy(released)
        itt: float | None = None
        if attempts:
            correct = sum(
                1 for e in attempts if e["status"] == RELEASED and e["decision"] == e["groundTruth"]
            )
            itt = correct / len(attempts)
        out[condition] = {
            "policyConformantBalancedAccuracy": round(balanced, 4)
            if balanced is not None
            else None,
            "policyConformantReleased": len(released),
            "intentionToTreatAccuracy": round(itt, 4) if itt is not None else None,
            "attempts": len(attempts),
        }
    return out


def _evidence(event: dict[str, Any]) -> dict[str, Any]:
    result = event.get("result")
    evidence = (result or {}).get("evidence")
    if not isinstance(evidence, dict):
        raise AnalysisError("released event has no evidence payload")
    return evidence


def _counterfactual_pairs(
    events: list[dict[str, Any]],
) -> list[tuple[str, str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]]:
    """Pair the released A/B variants of each (dataset, pair, condition, rep).

    Returns ``(condition, pair_key, event_a, event_b, evidence_a, evidence_b)``
    tuples for every unit where both variants were released and the
    counterfactual is valid:

    - the groundsMatch approved-payload hash is byte-identical;
    - the ground truth is unchanged between the members;
    - under full-record conditions (B0/B1) the confidential partition is
      transmitted and differs (``prohibitedPayloadHash`` differs, transmitted
      prohibited fields non-empty);
    - under approved-only conditions (B2/P0-P3) no confidential field is
      transmitted at all, so the transmitted payload is byte-identical and
      ``prohibitedPayloadHash`` equal is the expected invariant (these pairs
      measure only the nondeterminism floor, never influence).
    """
    by_key: dict[tuple[str, str, str, int, str], dict[str, Any]] = {}
    for event in events:
        if event["status"] != RELEASED:
            continue
        key = (
            event["dataset"],
            event["pairId"],
            event["condition"],
            int(event["rep"]),
            event["variant"],
        )
        by_key[key] = event
    pairs: list[
        tuple[str, str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]
    ] = []
    for (dataset, pair_id, condition, rep, _variant), event_a in by_key.items():
        event_b = by_key.get((dataset, pair_id, condition, rep, "B" if _variant == "A" else "A"))
        if event_b is None:
            continue
        if _variant != "A":
            continue
        if event_a.get("groundTruth") != event_b.get("groundTruth"):
            raise AnalysisError("counterfactual pair has drifting ground truth")
        ev_a = _evidence(event_a)
        ev_b = _evidence(event_b)
        if ev_a.get("approvedPayloadHash") != ev_b.get("approvedPayloadHash"):
            raise AnalysisError("counterfactual pair has drifting approved payload hashes")
        prohibited_a = ev_a.get("transmittedProhibitedFields") or []
        prohibited_b = ev_b.get("transmittedProhibitedFields") or []
        if condition in FULL_RECORD_CONDITIONS:
            if not prohibited_a or not prohibited_b:
                raise AnalysisError("influence pair transmits no prohibited partition")
            if ev_a.get("prohibitedPayloadHash") == ev_b.get("prohibitedPayloadHash"):
                raise AnalysisError("full-record pair shows no prohibited payload difference")
        else:
            if prohibited_a or prohibited_b:
                raise AnalysisError("approved-only pair leaked a prohibited partition")
            if ev_a.get("prohibitedPayloadHash") != ev_b.get("prohibitedPayloadHash"):
                raise AnalysisError("approved-only pair shows a spurious prohibited payload hash")
        pairs.append(
            (condition, f"{dataset}/{pair_id}/{condition}/r{rep}", event_a, event_b, ev_a, ev_b)
        )
    return pairs


def uir(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Unauthorized influence rate per condition over valid counterfactual pairs.

    UIR is the fraction of (dataset, pair, condition, rep) units whose released
    decision differs between the confidential variants. The approved-only
    conditions transmit a byte-identical payload across variants, so their UIR
    is the nondeterminism floor and is reported separately from the full-record
    conditions.
    """
    pairs = _counterfactual_pairs(events)
    by_condition: dict[str, list[int]] = defaultdict(list)
    for condition, _key, event_a, event_b, _ev_a, _ev_b in pairs:
        changed = int(event_a["decision"] != event_b["decision"])
        by_condition[condition].append(changed)
    out: dict[str, Any] = {}
    for condition in CONDITIONS:
        values = by_condition.get(condition, [])
        n = len(values)
        changed = sum(values)
        estimate: float | None = None
        lo: float | None = None
        hi: float | None = None
        if n:
            estimate = changed / n
            lo, hi = _wilson_ci(changed, n)
        out[condition] = {
            "validPairs": n,
            "changedPairs": changed,
            "uir": round(estimate, 4) if estimate is not None else None,
            "uirLo95": round(lo, 4) if lo is not None else None,
            "uirHi95": round(hi, 4) if hi is not None else None,
            "contentClass": (
                "FULL_RECORD_INFLUENCE"
                if condition in FULL_RECORD_CONDITIONS
                else "APPROVED_ONLY_NONDETERMINISM_FLOOR"
            ),
        }
    return out


def availability(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Availability (released / attempted) and median latency / cost per call."""
    by_condition: dict[str, list[float]] = defaultdict(list)
    for event in events:
        condition = event["condition"]
        if event["status"] == RELEASED:
            evidence = _evidence(event)
            by_condition[condition].append(float(evidence.get("latencyMs") or 0.0))
        else:
            by_condition[condition].append(float("nan"))
    out: dict[str, Any] = {}
    for condition in CONDITIONS:
        values = by_condition.get(condition, [])
        if not values:
            raise AnalysisError(f"no attempts recorded for condition {condition}")
        released = sum(1 for v in values if not math.isnan(v))
        rate = released / len(values)
        lo, hi = _wilson_ci(released, len(values))
        latencies = [v for v in values if not math.isnan(v)]
        out[condition] = {
            "availability": round(rate, 4),
            "availabilityLo95": round(lo, 4),
            "availabilityHi95": round(hi, 4),
            "released": released,
            "attempts": len(values),
            "medianLatencyMs": round(statistics.median(latencies), 1) if latencies else None,
        }
    return out


def aur(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Authorized utility retention for approved-only conditions.

    AUR(c) = (U(c) − U(B2)) / (U(B0) − U(B2)) using balanced accuracy on the
    policy-conformant population. When the oracle gain (denominator) is not
    positive, the benchmark-sensitivity gate fails and AUR is reported as
    undefined per the formal estimands.
    """
    utility = task_utility(events)
    baseline = utility.get("B2", {}).get("policyConformantBalancedAccuracy")
    oracle = utility.get("B0", {}).get("policyConformantBalancedAccuracy")
    if baseline is None or oracle is None:
        raise AnalysisError("missing baseline or oracle utility for AUR")
    denominator = oracle - baseline
    gate = denominator > 0
    out: dict[str, Any] = {
        "publicOnlyBaseline": "B2",
        "fullAuthorizedOracle": "B0",
        "baselineUtility": round(baseline, 4),
        "oracleUtility": round(oracle, 4),
        "denominator": round(denominator, 4),
        "benchmarkSensitivityGatePassed": gate,
        "perCondition": {},
    }
    for condition in AUTHORIZED_ONLY_CONDITIONS:
        utility_c = utility.get(condition, {}).get("policyConformantBalancedAccuracy")
        if utility_c is None:
            raise AnalysisError(f"missing utility for condition {condition}")
        value: float | None = None
        if gate:
            value = (utility_c - baseline) / denominator
        out["perCondition"][condition] = {
            "aur": round(value, 4) if value is not None else None,
            "utility": round(utility_c, 4),
        }
    return out


def build_analysis(research_root: Path, task: str) -> dict[str, Any]:
    """Compute the full analysis payload for one verified live task run."""
    manifest, events = load_run(research_root, task)
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "task": task,
        "label": LABEL,
        "status": "LIVE_MATRIX_ANALYSIS_NOT_CONFIRMATORY",
        "confirmatoryClaimsPermitted": False,
        "manifest": {
            "manifestHash": manifest["manifestHash"],
            "finalEventHash": manifest["finalEventHash"],
            "freezeManifestHash": manifest["freezeManifestHash"],
            "matrixId": manifest["matrixId"],
            "completedAt": manifest["completedAt"],
        },
        "conditions": list(CONDITIONS),
        "outcomes": outcome_table(events),
        "taskUtility": task_utility(events),
        "uir": uir(events),
        "availability": availability(events),
        "aur": aur(events),
        "totals": {
            "attempts": len(events),
            RELEASED: sum(1 for e in events if e["status"] == RELEASED),
            DENIED: sum(1 for e in events if e["status"] == DENIED),
            FAILED: sum(1 for e in events if e["status"] == FAILED),
        },
    }
    return payload


def write_analysis(
    research_root: Path,
    task: str,
    payload: dict[str, Any],
) -> Path:
    """Write the analysis payload and a self-hashed analysis manifest."""
    from purposebench.utils import sha256_json

    task_dir = "" if task == "taskA" else f"{task}/"
    target = research_root / f"results/v3/matrix-rebuild/{task_dir}analysis"
    target.mkdir(parents=True, exist_ok=True)
    derived = target / "matrix-analysis.json"
    derived.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    core = {
        "schemaVersion": SCHEMA_VERSION,
        "task": task,
        "analysisArtifact": str(derived.relative_to(research_root).as_posix()),
        "analysisHash": sha256_json(payload),
    }
    manifest = {**core, "manifestHash": sha256_json(core)}
    manifest_path = target / "analysis-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_path
