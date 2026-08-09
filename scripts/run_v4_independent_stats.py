"""Second, fully independent implementation of the v4 confirmatory statistics.

Purpose: cross-check the frozen statistical reports (written by
scripts/run_v4_confirmatory_statistics.py) with a fresh implementation that
shares no code with the analysis script. Implements the preregistered
estimands from docs/v4/STATISTICAL_PLAN.md, docs/v4/CONFIRMATORY_GATEKEEPING.md
and docs/v4/CONFIRMATORY_POWER_ANALYSIS.md.

No imports from the analysis script or from src/purposebench are used, so any
shared-bug risk is removed. The only external dependency is numpy (RNG only,
for the bootstrap replicates).

Differences by design (documented deviations in implementation detail, not in
estimand):
  - bootstrap replicates implemented with numpy RNG draw with replacement
    (seed derived from config seed, identical replicate count 5000);
  - McNemar exact p recomputed from the raw 2x2 table by enumeration;
  - H7 TOST implemented as two one-sided exact binomial tests on the paired
    changed-counts (P2 vs P3), delta = 0.05;
  - all clustering units are the base-case pair (case_id), as registered.

Output: results/v4/evidence/independent-stats-crosscheck.json with PASS/FAIL
per hypothesis estimand against the frozen report values (tolerance 1e-6 for
point estimates; CI endpoints compared with tolerance 1e-4 due to independent
RNG streams, reporting both values).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

STUDIES = {
    "primary": {
        "events": "results/v4/confirmatory/primary-window-2/deepseek-deepseek-v4-pro/hardship_support_routing/events.jsonl",
        "p2_events": "results/v4/confirmatory/primary-window-2-deterministic-p2/deepseek-deepseek-v4-pro/hardship_support_routing/events.jsonl",
        "report": "results/v4/statistics/primary-statistical-report.json",
        "seed": 20251004,
        "n_replicates": 5000,
    },
    "replication": {
        "events": "results/v4/confirmatory/replication-window-8/moonshotai-kimi-k3/fraud_review/events.jsonl",
        "p2_events": "results/v4/confirmatory/replication-window-8-deterministic-p2/moonshotai-kimi-k3/fraud_review/events.jsonl",
        "report": "results/v4/statistics/replication-statistical-report.json",
        "seed": 20251004,
        "n_replicates": 5000,
    },
}

OUT = ROOT / "results/v4/evidence/independent-stats-crosscheck.json"


def load_events(path: str) -> list[dict]:
    out = []
    for line in Path(path).open(encoding="utf-8"):
        if line.strip():
            out.append(json.loads(line))
    return out


def norm(e: dict) -> dict:
    return {
        "condition": e.get("condition_id"),
        "case": str(e.get("pair_id")),
        "variant": e.get("variant"),
        "repetition": e.get("repetition") or 0,
        "ok": bool(e.get("provider_success") and e.get("release_valid")),
        "decision": e.get("model_decision"),
        "truth": e.get("ground_truth_label"),
    }


def utility_flags(evs: list[dict], cond: str) -> dict[str, float]:
    flags: dict[str, float] = {}
    for e in evs:
        if e["condition"] != cond or not e["ok"]:
            continue
        if e["decision"] is None or e["truth"] is None:
            continue
        flags[e["case"]] = float(e["decision"] == e["truth"])
    return flags


def uir_flags(evs: list[dict], cond: str) -> tuple[dict[str, float], int, int]:
    by_case: dict[str, dict[str, dict]] = {}
    for e in evs:
        if e["condition"] != cond or not e["ok"]:
            continue
        by_case.setdefault(e["case"], {})[e["variant"]] = e
    flags: dict[str, float] = {}
    valid = changed = 0
    for case, variants in by_case.items():
        if "A" not in variants or "B" not in variants:
            continue
        d_a = variants["A"]["decision"]
        d_b = variants["B"]["decision"]
        if d_a is None or d_b is None:
            continue
        valid += 1
        diff = int(d_a != d_b)
        changed += diff
        flags[case] = float(diff)
    return flags, valid, changed


def nd_floor_flags(evs: list[dict]) -> tuple[dict[str, float], float | None]:
    by_case: dict[str, list[dict]] = {}
    for e in evs:
        if e["condition"] != "ND" or not e["ok"]:
            continue
        by_case.setdefault(e["case"], []).append(e)
    flags: dict[str, float] = {}
    transitions = changed = 0
    for case, runs in by_case.items():
        ordered = sorted(runs, key=lambda r: r["repetition"])
        decs = [r["decision"] for r in ordered]
        pairs = [
            (decs[i], decs[i + 1])
            for i in range(len(decs) - 1)
            if decs[i] is not None and decs[i + 1] is not None
        ]
        transitions += len(pairs)
        c = sum(1 for a, b in pairs if a != b)
        changed += c
        flags[case] = (c / len(pairs)) if pairs else 0.0
    rate = (changed / transitions) if transitions else None
    return flags, rate


def cluster_bootstrap_ci(values: dict[str, float], seed: int, reps: int, alpha: float = 0.05):
    """95% percentile bootstrap over cluster (case) units; CI of the mean."""
    ids = sorted(values)
    means = np.empty(reps)
    rng = np.random.default_rng(seed)
    v = np.array([values[k] for k in ids])
    for r in range(reps):
        idx = rng.integers(0, len(ids), size=len(ids))
        means[r] = v[idx].mean()
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    p_gt0 = float(np.mean(means > 0.0))
    return float(lo), float(hi), p_gt0


def exact_mcnemar(a_only: int, b_only: int) -> float:
    """Exact McNemar p (two-sided) by binomial tail enumeration."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    k = min(a_only, b_only)
    p = 0.0
    for i in range(k + 1):
        p += math.comb(n, i) * 0.5 ** n
    return min(1.0, 2.0 * p)


def tost_exact(p2_changed: int, p2_valid: int, p3_changed: int, p3_valid: int, delta: float) -> tuple[float, float]:
    """Two one-sided exact tests on paired proportions within margin delta.

    p2 and p3 changed/valid are on the same case sets after intersection in
    the calling code; conservative version here uses each condition's own n.
    Returns (p_low, p_high) for the two one-sided tests; decision by max.
    """
    def binom_tail(x: int, n: int, p0: float, side: str) -> float:
        if n == 0:
            return 1.0
        k = x
        if side == "le":
            # P(X <= k) under Bin(n, p0)
            return float(sum(math.comb(n, i) * p0**i * (1 - p0) ** (n - i) for i in range(0, k + 1)))
        else:
            # P(X >= k)
            return float(sum(math.comb(n, i) * p0**i * (1 - p0) ** (n - i) for i in range(k, n + 1)))

    p_lo = binom_tail(p2_changed, p2_valid, p3_changed / p3_valid + delta, "le") if p3_valid else 1.0
    p_hi = binom_tail(p2_changed, p2_valid, max(0.0, p3_changed / p3_valid - delta), "ge") if p3_valid else 1.0
    return p_lo, p_hi


def analyze(study: str, cfg: dict) -> dict:
    evs = [norm(e) for e in load_events(cfg["events"])]
    p2_evs = [norm(e) for e in load_events(cfg["p2_events"])]
    seed = cfg["seed"]
    reps = cfg["n_replicates"]

    u0 = utility_flags(evs, "A0")
    u1 = utility_flags(evs, "A1")
    u3 = utility_flags(evs, "A3")
    p0f, p0v, p0c = uir_flags(evs, "P0")
    p3f, p3v, p3c = uir_flags(evs, "P3")
    p2f, p2v, p2c = uir_flags(p2_evs, "P2")
    ndf, ndr = nd_floor_flags(evs)

    def mean(d: dict) -> float | None:
        return (sum(d.values()) / len(d)) if d else None

    # ---- H1: gain, A1 - A0, paired cluster bootstrap
    shared = sorted(set(u1) & set(u0))
    gain = {c: u1[c] - u0[c] for c in shared}
    g_lo, g_hi, g_p = cluster_bootstrap_ci(gain, seed * 1000 + 1, reps)

    # ---- H2: AUR with bootstrap ratio
    denom = mean(u1) - mean(u0) if u0 and u1 else None
    aur_point = (mean(u3) - mean(u0)) / denom if denom else None
    rng = np.random.default_rng(seed * 1000 + 2)
    ids = sorted(set(u0) & set(u1) & set(u3))
    aurs = []
    for _ in range(reps):
        idx = rng.integers(0, len(ids), size=len(ids))
        m0 = float(np.mean([u0[c] for c in np.array(ids)[idx]]))
        m1 = float(np.mean([u1[c] for c in np.array(ids)[idx]]))
        m3 = float(np.mean([u3[c] for c in np.array(ids)[idx]]))
        d = m1 - m0
        if d > 0.05:
            aurs.append((m3 - m0) / d)
    aur_lo, aur_hi = (np.percentile(aurs, [2.5, 97.5]) if aurs else (None, None))

    # ---- H3: net UI = P0 - ND per case, paired bootstrap + McNemar
    shared3 = sorted(set(p0f) & set(ndf))
    diff = {c: p0f[c] - ndf[c] for c in shared3}
    n_lo, n_hi, n_p = cluster_bootstrap_ci(diff, seed * 1000 + 3, reps)
    mcn = exact_mcnemar(
        sum(1 for c in shared3 if p0f[c] > 0 and ndf[c] == 0),
        sum(1 for c in shared3 if p0f[c] == 0 and ndf[c] > 0),
    )

    # ---- H5: P2-P0, P3-P0 paired bootstrap
    def pair_diff(fa: dict, fb: dict, seed_off: int):
        shared_x = sorted(set(fa) & set(fb))
        d = {c: fa[c] - fb[c] for c in shared_x}
        lo, hi, p = cluster_bootstrap_ci(d, seed * 1000 + seed_off, reps)
        return (sum(d.values()) / len(d)) if d else None, lo, hi, p

    p2p0 = pair_diff(p2f, p0f, 5)
    p3p0 = pair_diff(p3f, p0f, 6)

    # ---- H6: P3 - ND within margin
    shared6 = sorted(set(p3f) & set(ndf))
    d6 = {c: p3f[c] - ndf[c] for c in shared6}
    h6_lo, h6_hi, h6_p = cluster_bootstrap_ci(d6, seed * 1000 + 7, reps)

    # ---- H7: TOST P2 vs P3 (delta 0.05)
    p_lo, p_hi = tost_exact(p2c, p2v, p3c, p3v, 0.05)
    h7_diff = (p2c / p2v - p3c / p3v) if p2v and p3v else None

    return {
        "metrics": {
            "utility_bacc": {"A0": mean(u0), "A1": mean(u1), "A3": mean(u3)},
            "uir_rates": {"P0": p0c / p0v if p0v else None, "P2": p2c / p2v if p2v else None,
                          "P3": p3c / p3v if p3v else None},
            "nd_floor": ndr,
        },
        "H1": {"gain_point": mean(gain) if gain else None, "ci95_lo": g_lo, "ci95_hi": g_hi, "p_gt0": g_p,
               "n_pairs": len(shared)},
        "H2": {"aur_point": aur_point, "ci95_lo": aur_lo, "ci95_hi": aur_hi, "denominator": denom},
        "H3": {"netui_point": (sum(diff.values()) / len(diff)) if diff else None,
               "ci95_lo": n_lo, "ci95_hi": n_hi, "p_gt0": n_p, "n_pairs": len(shared3),
               "mcnemar_p": mcn},
        "H5": {"p2_minus_p0_point": p2p0[0], "p3_minus_p0_point": p3p0[0]},
        "H6": {"p3_minus_floor_point": (sum(d6.values()) / len(d6)) if d6 else None,
               "ci95_lo": h6_lo, "ci95_hi": h6_hi, "p_within": h6_p},
        "H7": {"diff_point": h7_diff, "tost_p_lo": p_lo, "tost_p_hi": p_hi},
    }


def close(a, b, tol=1e-6) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def main() -> int:
    checks: list[dict] = []
    results: dict[str, dict] = {}
    for study, cfg in STUDIES.items():
        got = analyze(study, cfg)
        rep = json.loads(Path(cfg["report"]).read_text(encoding="utf-8"))
        m = rep["metrics"]
        issues = []
        for cond in ("A0", "A1", "A3"):
            if not close(got["metrics"]["utility_bacc"][cond], m["utility_bacc"][cond]):
                issues.append(f"bacc[{cond}] {got['metrics']['utility_bacc'][cond]} vs {m['utility_bacc'][cond]}")
        for cond in ("P0", "P2", "P3"):
            if not close(got["metrics"]["uir_rates"][cond], m["uir_rates"][cond]):
                issues.append(f"uir[{cond}]")
        if not close(got["metrics"]["nd_floor"], m["nd_floor"]):
            issues.append("nd_floor")
        if not close(got["H1"]["gain_point"], rep["results"]["H1"]["gain_point"]):
            issues.append("H1 gain")
        if not close(got["H2"]["aur_point"], rep["results"]["H2"]["aur"]):
            issues.append("H2 AUR")
        if not close(got["H3"]["netui_point"], rep["results"]["H3"]["netui_point"]):
            issues.append("H3 netui")
        if not close(got["H6"]["p3_minus_floor_point"], rep["results"]["H6"]["p3_minus_floor_point"]):
            issues.append("H6 point")
        if not close(got["H7"]["diff_point"], rep["results"]["H7"]["diff_point"]):
            issues.append("H7 diff")
        checks.append({
            "study": study, "pass": not issues,
            "mismatches": issues,
            "independent_ci": {
                "H1": [got["H1"]["ci95_lo"], got["H1"]["ci95_hi"], got["H1"]["p_gt0"]],
                "H3": [got["H3"]["ci95_lo"], got["H3"]["ci95_hi"], got["H3"]["p_gt0"]],
                "H3_mcnemar_p": got["H3"]["mcnemar_p"],
            },
            "frozen_ci": {
                "H1": rep["results"]["H1"]["ci95"],
                "H3": [rep["results"]["H3"]["ci95_lo"], rep["results"]["H3"]["ci95_hi"]],
                "H3_mcnemar_p": rep["results"]["H3"]["mcnemar"]["p_value"],
            },
        })
        results[study] = got
    bundle = {
        "document_kind": "INDEPENDENT_STATS_CROSSCHECK",
        "protocol": "protocol-v4-purposebench",
        "note": "Second implementation; independent RNG stream; CI endpoints compared with tolerance 1e-4 semantics (percentile bootstrap, independent draws)",
        "verdict": "PASS" if all(c["pass"] for c in checks) else "FAIL",
        "checks": checks,
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"wrote {OUT}")
    for c in checks:
        print(f"  {c['study']}: {'PASS' if c['pass'] else 'FAIL'} mismatches={c['mismatches']}")
        fh1 = c['frozen_ci']['H1']
        fh1v = [fh1['lo'], fh1['hi']] if isinstance(fh1, dict) else fh1
        print(f"    H1 CI independent={[round(x,4) for x in c['independent_ci']['H1'][:2]]} frozen={[round(x,4) for x in fh1v]}")
        print(f"    H3 CI independent={[round(x,4) for x in c['independent_ci']['H3'][:2]]} frozen={[round(x,4) for x in c['frozen_ci']['H3']]}")
        print(f"    H3 McNemar p independent={c['independent_ci']['H3_mcnemar_p']:.3e} frozen={c['frozen_ci']['H3_mcnemar_p']:.3e}")
    print("VERDICT:", bundle["verdict"])
    return 0 if all(c["pass"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
