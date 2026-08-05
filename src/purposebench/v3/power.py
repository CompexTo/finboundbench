"""Prospective paired-binary power calculations for protocol v3.

The calculation integrates conditional exact McNemar rejection probabilities
over the prospective distribution of the number of discordant pairs. It does
not read benchmark outcomes.
"""

from __future__ import annotations

from functools import cache
from typing import Literal

import numpy as np
from scipy.stats import binom

Alternative = Literal["two-sided", "greater"]


def _validate_probability(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be within [0, 1]")


@cache
def _conditional_rejection_probability(
    discordant: int,
    *,
    alternative_probability: float,
    alpha: float,
    alternative: Alternative,
) -> float:
    """Return exact-test rejection probability for a discordant count."""

    if discordant == 0:
        return 0.0
    counts = np.arange(discordant + 1)
    null_mass = binom.pmf(counts, discordant, 0.5)
    if alternative == "greater":
        p_values = binom.sf(counts - 1, discordant, 0.5)
    elif alternative == "two-sided":
        # This is the standard exact two-sided binomial definition used by
        # scipy.stats.binomtest: sum null outcomes no more likely than the
        # observed outcome. The tolerance prevents floating-point tie breaks.
        p_values = np.asarray(
            [
                float(null_mass[null_mass <= mass * (1.0 + 1e-7)].sum())
                for mass in null_mass
            ]
        )
    else:  # pragma: no cover - guarded by the public validator
        raise ValueError(f"unsupported alternative: {alternative}")
    alternative_mass = binom.pmf(
        counts,
        discordant,
        alternative_probability,
    )
    return float(alternative_mass[p_values <= alpha].sum())


def exact_mcnemar_power(
    n_pairs: int,
    p_baseline_only: float,
    p_comparator_only: float,
    *,
    alpha: float = 0.05,
    alternative: Alternative = "two-sided",
) -> float:
    """Compute prospective exact conditional McNemar power.

    ``p_baseline_only`` is P(baseline event, comparator no event), and
    ``p_comparator_only`` is the reverse discordance probability.
    """

    if n_pairs <= 0:
        raise ValueError("n_pairs must be positive")
    _validate_probability("p_baseline_only", p_baseline_only)
    _validate_probability("p_comparator_only", p_comparator_only)
    _validate_probability("alpha", alpha)
    discordance_probability = p_baseline_only + p_comparator_only
    if discordance_probability > 1.0:
        raise ValueError("discordance probabilities cannot sum above 1")
    if discordance_probability == 0.0:
        return 0.0
    if alternative not in {"two-sided", "greater"}:
        raise ValueError(f"unsupported alternative: {alternative}")

    conditional_alternative = p_baseline_only / discordance_probability
    return float(
        sum(
            binom.pmf(
                discordant,
                n_pairs,
                discordance_probability,
            )
            * _conditional_rejection_probability(
                discordant,
                alternative_probability=conditional_alternative,
                alpha=alpha,
                alternative=alternative,
            )
            for discordant in range(1, n_pairs + 1)
        )
    )


def minimum_pairs_for_power(
    target_power: float,
    p_baseline_only: float,
    p_comparator_only: float,
    *,
    alpha: float = 0.05,
    alternative: Alternative = "two-sided",
    maximum_pairs: int = 10_000,
) -> int:
    """Find the first integer pair count meeting a target power."""

    _validate_probability("target_power", target_power)
    if target_power == 0.0:
        return 1
    for n_pairs in range(1, maximum_pairs + 1):
        if exact_mcnemar_power(
            n_pairs,
            p_baseline_only,
            p_comparator_only,
            alpha=alpha,
            alternative=alternative,
        ) >= target_power:
            return n_pairs
    raise ValueError("target power was not reached within maximum_pairs")


def protocol_v3_power_report() -> dict[str, object]:
    """Return the registered prospective scenarios and exact results."""

    scenarios = (
        (
            "h4_strong",
            0.20,
            0.05,
            0.025,
            "two-sided",
        ),
        (
            "h4_conservative",
            0.14,
            0.04,
            0.025,
            "two-sided",
        ),
        (
            "h1_authorized_utility",
            0.16,
            0.06,
            0.05,
            "greater",
        ),
    )
    rows: list[dict[str, object]] = []
    for name, p10, p01, alpha, alternative in scenarios:
        typed_alternative: Alternative = alternative  # type: ignore[assignment]
        rows.append(
            {
                "name": name,
                "pBaselineOnly": p10,
                "pComparatorOnly": p01,
                "alpha": alpha,
                "alternative": alternative,
                "power": {
                    str(n): round(
                        exact_mcnemar_power(
                            n,
                            p10,
                            p01,
                            alpha=alpha,
                            alternative=typed_alternative,
                        ),
                        6,
                    )
                    for n in (80, 100, 200)
                },
                "minimumPairsFor80Percent": minimum_pairs_for_power(
                    0.80,
                    p10,
                    p01,
                    alpha=alpha,
                    alternative=typed_alternative,
                    maximum_pairs=500,
                ),
            }
        )
    return {
        "schemaVersion": "finboundbench.power-analysis.v3",
        "prospectiveOnly": True,
        "readsOutcomeData": False,
        "method": "conditional_exact_mcnemar_integrated_over_discordant_count",
        "scenarios": rows,
    }
