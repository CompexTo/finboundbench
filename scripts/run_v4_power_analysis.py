"""Confirmatory power analysis for protocol-v4 purpose-selectivity (Fix 1/2/6a).

Monte-Carlo power over the actual CONFIRMATORY pair stream using the repo's own
paired-cluster bootstrap (src/purposebench/v4/statistics.bootstrap_ci), so the
planning numbers are grounded in the real pair stream and contrast-truth model,
not a closed-form asymptotic guess.

Shrinkage rule (winner's-curse): use the discovery CI LOWER BOUNDS as planning
effects, not the discovery point estimates.
  primary      deepseek x hardship     CI LB 0.167
  replication  kimi x fraud            CI LB 0.063

Registered pre-execution amendment (2026-08-07, bound in Freeze 1 regeneration
before any live confirmatory call): the frozen CONFIRMATORY pool holds exactly
120 fraud pairs; n=500 replication is infeasible without breaking the frozen
dataset manifest. The replication therefore runs the COMPLETE frozen pool
(n=120) and the registered planning effect for the replication is WIDENED to
0.15 (the smallest round effect with power >= 0.80 at n=120; MC power 0.95).
Achieved power at the original shrunk effect (0.063) with n=120 is 0.30 —
a registered resolution limitation, reported honestly, not a redesign.

ND arm sizing (Fix 2): one-sided 95% UCB by rule of three = 3/n must be
<= H6_margin/2. Registered H6 margin = 0.05 (decision-relevance, see doc).

Per-pair call budget (minimal necessary conditions): A0, A1, A3, P0, P3 once
each + ND 3x = 8 provider calls per pair.

Writes:
  results/v4/statistics/power-estimate.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from purposebench.v4 import statistics as st

ROOT = Path(__file__).resolve().parents[1]

ALPHA = 0.05
POWER_TARGET = 0.80
CONFIRMATORY_BUDGET_EUR = 40.0  # FOUNDER-CONFIRMED hard budget (2026-08-07 decision)
H6_MARGIN = 0.05
ND_UCB_TARGET = H6_MARGIN / 2.0
RESERVATION_EUR = 0.02
OBSERVED_MEAN_EUR = 0.00144  # measured live mean per provider-billed call (n=720, eligibility)
OBSERVED_SAFETY_MULTIPLIER = 5.0  # reserve: plan on 5x observed economics
CALLS_PER_PAIR = 8  # A0,A1,A3,P0,P3 (5) + ND x3
N_BOOT = 2500

STUDIES = [
    {
        "study": "primary_deepseek_hardship",
        "shrunk_effect": 0.167,
        "discovery_point": 0.318,
        "seed": 20261001,
    },
    {
        "study": "replication_kimi_fraud",
        "shrunk_effect": 0.063,
        "planning_effect_amended": 0.15,
        "discovery_point": 0.190,
        "seed": 20261002,
    },
]

# Registered pre-execution amendment: replication n is capped at the complete
# frozen CONFIRMATORY pool (120 fraud pairs). Do not select beyond it.
REPLICATION_POOL_CAP = 120


def nd_arm_size() -> tuple[int, float]:
    n = max(3, math.ceil(3.0 / ND_UCB_TARGET))
    return n, 3.0 / n


def power_at(effect: float, n: int, seed: int, reps: int = 40) -> tuple[float, float]:
    """Fraction of paired-bootstrap CIs with LB > 0, mean LB (paired-BACC model).

    Per-case contrast is a normal draw with mean = planning effect and sd 0.5
    (the sd of a single-case balanced-accuracy contribution under a 2-class
    model is at most 0.5). Cluster bootstrap over cases mirrors the protocol's
    H1 test on the A1-A0 difference.
    """
    rng = np.random.default_rng(seed)
    passes = 0
    mean_lb = 0.0
    for rep in range(reps):
        cases = rng.normal(effect, 0.5, size=n)
        lb, _ub = st.bootstrap_ci(
            [(f"c{i}", float(cases[i])) for i in range(n)],
            n_boot=N_BOOT,
            seed=seed + rep,
        )
        if lb > 0:
            passes += 1
        mean_lb += lb
    return passes / reps, mean_lb / reps


def main() -> int:
    n_nd, nd_ucb = nd_arm_size()
    sweep_ns = [60, 100, 150, 200, 300, 500]
    studies_out: list[dict[str, object]] = []
    for spec in STUDIES:
        eff = spec["shrunk_effect"]
        sweep = []
        for n in sweep_ns:
            power, mean_lb = power_at(eff, n, seed=spec["seed"])
            sweep.append({"n_pairs": n, "bootstrap_power": round(power, 3), "mean_lower_bound": round(mean_lb, 4)})
            print(f"  [{spec['study']}] n={n} power={power:.3f}", flush=True)
        chosen = next((row for row in sweep if row["bootstrap_power"] >= POWER_TARGET), sweep[-1])
        entry: dict[str, object] = {
            "study": spec["study"],
            "shrunk_planning_effect": eff,
            "discovery_point_estimate": spec["discovery_point"],
            "power_sweep": sweep,
        }
        if spec["study"] == "replication_kimi_fraud":
            amended_eff = spec["planning_effect_amended"]
            entry["planning_effect_amended"] = amended_eff
            entry["pool_cap_applies"] = True
            entry["pool_cap_n_pairs"] = REPLICATION_POOL_CAP
            power_cap, mean_lb_cap = power_at(amended_eff, REPLICATION_POOL_CAP, seed=spec["seed"])
            power_cap_shrunk, _ = power_at(eff, REPLICATION_POOL_CAP, seed=spec["seed"] + 1)
            entry["amended_registered_n_pairs"] = REPLICATION_POOL_CAP
            entry["amended_power_at_registered_margin"] = round(power_cap, 3)
            entry["amended_mean_lower_bound"] = round(mean_lb_cap, 4)
            entry["amended_power_at_original_shrunk_effect"] = round(power_cap_shrunk, 3)
            entry["amendment_justification"] = (
                "frozen CONFIRMATORY pool holds exactly 120 fraud pairs; n=500 infeasible "
                "without breaking the frozen dataset manifest; registered wider planning "
                "margin 0.15 (smallest round effect with power >= 0.80 at n=120), "
                "registered before any live confirmatory call"
            )
        else:
            entry["n_selected"] = chosen["n_pairs"]
            entry["power_at_selected"] = chosen["bootstrap_power"]
        studies_out.append(entry)

    n_primary = studies_out[0]["n_selected"]
    n_replication = REPLICATION_POOL_CAP
    primary_calls = n_primary * CALLS_PER_PAIR
    replication_calls = n_replication * CALLS_PER_PAIR
    total_calls = primary_calls + replication_calls
    est_cost_eur_reservation = total_calls * RESERVATION_EUR
    est_cost_eur_observed = total_calls * OBSERVED_MEAN_EUR * OBSERVED_SAFETY_MULTIPLIER

    result = {
        "protocol": "protocol-v4-purposebench",
        "analysis_kind": "montecarlo_paired_bootstrap_shrunk_effect",
        "alpha": ALPHA,
        "power_target": POWER_TARGET,
        "h6_margin_registered": H6_MARGIN,
        "nd_ucb_target": ND_UCB_TARGET,
        "n_nd": n_nd,
        "nd_point_floor_observation": 0.0,
        "nd_ucb_achieved": nd_ucb,
        "nd_ucb_margin_condition": f"3/n_ND ({nd_ucb:.4f}) <= margin/2 ({ND_UCB_TARGET:.4f})",
        "studies": studies_out,
        "n_primary": int(n_primary),
        "n_replication": int(n_replication),
        "calls_per_pair": CALLS_PER_PAIR,
        "primary_total_calls": primary_calls,
        "replication_total_calls": replication_calls,
        "total_calls": total_calls,
        "est_cost_eur_reservation_ceiling": est_cost_eur_reservation,
        "est_cost_eur_observed_x5": est_cost_eur_observed,
        "hard_budget_eur": CONFIRMATORY_BUDGET_EUR,
        "within_hard_budget": est_cost_eur_observed <= CONFIRMATORY_BUDGET_EUR,
        "reservation_ceiling_exceeds_budget": est_cost_eur_reservation > CONFIRMATORY_BUDGET_EUR,
    }
    out = ROOT / "results/v4/statistics/power-estimate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())