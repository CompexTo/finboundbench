"""Protocol-v4 statistical procedures (CONTRACT_V4.md section 6, owned by Agent 4).

All procedures operate on plain Python data (per-base-case values) so the
module is importable and testable without any run artifacts.

Implemented procedures:

- ``bootstrap_ci``: paired cluster bootstrap over base cases (percentile CI).
- ``exact_mcnemar``: exact McNemar test on paired 2x2 decision change
  (statsmodels ``mcnemar`` when available, binomial-sign fallback otherwise).
- ``paired_permutation_test``: paired permutation test for UIR_visible vs floor.
- ``wilson_ci`` / ``proportion_difference_ci``: Wilson score interval and a
  Newcombe-style difference interval.
- ``tost_equivalence``: two one-sided equivalence test on paired differences
  (margin ``delta``, default 0.10).
- ``holm_bonferroni``: pure-Python Holm-Bonferroni correction.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

try:
    from statsmodels.stats.contingency_tables import mcnemar as _statsmodels_mcnemar

    _HAS_STATSMODELS_MCNEMAR = True
except Exception:  # pragma: no cover - optional dependency
    _statsmodels_mcnemar = None
    _HAS_STATSMODELS_MCNEMAR = False


def _as_case_values(
    paired: Iterable[tuple[str, float]] | Mapping[str, float] | Sequence[float],
) -> dict[str, list[float]]:
    """Normalize per-base-case data to {base_case_id: [values]}."""
    by_case: dict[str, list[float]] = defaultdict(list)
    if isinstance(paired, Mapping):
        for key, value in paired.items():
            by_case[str(key)].append(float(value))
        return by_case
    for item in paired:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            case_id, value = item
            by_case[str(case_id)].append(float(value))
        else:
            by_case[f"case_{len(by_case)}"].append(float(item))
    return by_case


def bootstrap_ci(
    paired: Iterable[tuple[str, float]] | Mapping[str, float] | Sequence[float],
    n_boot: int = 5000,
    seed: int | None = None,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Percentile 95% CI from a paired cluster bootstrap over base cases.

    ``paired`` is per-base-case data (either ``{case_id: value}``,
    ``[(case_id, value), ...]``, or a flat list of values). Each bootstrap
    replicate resamples base cases with replacement and recomputes the mean of
    their values; the CI is the ``(alpha/2, 1-alpha/2)`` quantiles. Returns
    ``(nan, nan)`` when there is no data.
    """
    by_case = _as_case_values(paired)
    if not by_case:
        return (float("nan"), float("nan"))
    case_ids = sorted(by_case)
    if len(case_ids) < 2:
        estimate = float(np.mean([v for values in by_case.values() for v in values]))
        return (estimate, estimate)
    rng = np.random.default_rng(seed)
    estimates = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        sample_ids = rng.choice(case_ids, size=len(case_ids), replace=True)
        values = np.concatenate([np.asarray(by_case[cid], dtype=float) for cid in sample_ids])
        estimates[i] = values.mean()
    lo, hi = np.quantile(estimates, [alpha / 2, 1 - alpha / 2])
    return (float(lo), float(hi))


def exact_mcnemar(
    a: Sequence[Any], b: Sequence[Any]
) -> dict[str, Any]:
    """Exact McNemar test on paired binary decision-change indicators.

    ``a`` and ``b`` are per-base-case binary flags (e.g. decision changed under
    condition X vs condition Y). Builds the 2x2 discordance table and uses
    statsmodels' exact mcnemar when available, falling back to the binomial
    sign test on the discordant counts.
    """
    if len(a) != len(b):
        raise ValueError("a and b must have equal length")
    pairs = [(bool(a_i), bool(b_i)) for a_i, b_i in zip(a, b) if a_i is not None and b_i is not None]
    if not pairs:
        return {"n": 0, "p_value": 1.0, "method": "no_data"}
    both = sum(1 for x, y in pairs if x and y)
    a_only = sum(1 for x, y in pairs if x and not y)
    b_only = sum(1 for x, y in pairs if not x and y)
    neither = sum(1 for x, y in pairs if not x and not y)
    discordant = a_only + b_only
    if discordant == 0:
        p_value = 1.0
        method = "exact_mcnemar"
    elif _HAS_STATSMODELS_MCNEMAR and _statsmodels_mcnemar is not None:
        table = np.array([[both, a_only], [b_only, neither]], dtype=int)
        result = _statsmodels_mcnemar(table, exact=True)
        p_value = float(result.pvalue)
        method = "statsmodels.mcnemar.exact"
    else:  # pragma: no cover - fallback when statsmodels is missing
        from scipy.stats import binomtest

        p_value = float(binomtest(min(a_only, b_only), discordant, 0.5, alternative="two-sided").pvalue)
        method = "scipy.stats.binomtest.sign_test"
    return {
        "n": len(pairs),
        "both": both,
        "a_only": a_only,
        "b_only": b_only,
        "neither": neither,
        "discordant": discordant,
        "p_value": p_value,
        "method": method,
    }


def paired_permutation_test(
    a: Sequence[float],
    b: Sequence[float],
    *,
    n_perm: int = 10000,
    seed: int | None = None,
    alternative: str = "two-sided",
) -> dict[str, Any]:
    """Paired permutation (sign-flip) test of mean(a) vs mean(b).

    Null distribution generated by randomly flipping the sign of each
    per-base-case difference. ``alternative`` in {"two-sided", "greater",
    "less"}; returns observed statistic, p-value and the permutation seed.
    """
    if len(a) != len(b):
        raise ValueError("a and b must have equal length")
    diffs = np.asarray([x - y for x, y in zip(a, b) if x is not None and y is not None], dtype=float)
    if diffs.size == 0:
        return {"n": 0, "observed": None, "p_value": 1.0, "alternative": alternative}
    observed = float(diffs.mean())
    rng = np.random.default_rng(seed)
    permuted = np.empty(n_perm, dtype=float)
    for i in range(n_perm):
        signs = rng.choice([-1.0, 1.0], size=diffs.size)
        permuted[i] = float((signs * diffs).mean())
    if alternative == "greater":
        p_value = float((permuted >= observed).mean())
    elif alternative == "less":
        p_value = float((permuted <= observed).mean())
    else:
        p_value = float((np.abs(permuted) >= abs(observed)).mean())
    return {
        "n": int(diffs.size),
        "observed": observed,
        "p_value": p_value,
        "n_perm": n_perm,
        "seed": seed,
        "alternative": alternative,
    }


def wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% interval for a proportion; (nan, nan) when total <= 0."""
    if total <= 0:
        return (float("nan"), float("nan"))
    phat = successes / total
    denom = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denom
    half = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def proportion_difference_ci(
    k1: int, n1: int, k2: int, n2: int, z: float = 1.96
) -> tuple[float, float]:
    """Newcombe (Wilson-based) 95% CI for the difference of two proportions."""
    if n1 <= 0 or n2 <= 0:
        return (float("nan"), float("nan"))
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson_ci(k1, n1, z)
    l2, u2 = wilson_ci(k2, n2, z)
    diff = p1 - p2
    lo = diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (lo, hi)


def _paired_differences(
    a: Sequence[float], b: Sequence[float] | None, constant: float = 0.0
) -> np.ndarray:
    if b is None:
        return np.asarray(
            [x - constant for x in a if x is not None], dtype=float
        )
    if len(a) != len(b):
        raise ValueError("a and b must have equal length")
    return np.asarray(
        [x - y for x, y in zip(a, b) if x is not None and y is not None], dtype=float
    )


def tost_equivalence(
    a: Sequence[float],
    b: Sequence[float] | None = None,
    *,
    delta: float = 0.10,
    constant: float = 0.0,
) -> dict[str, Any]:
    """Two one-sided tests (TOST) for equivalence of paired means.

    H0: |mean(a - b)| >= delta; equivalence is concluded when ``p_tost`` < 0.05.
    When ``b`` is None, tests the single sample ``a`` against ``constant``
    (e.g. UIR_P3 against the ND floor). Uses a paired t-test on the
    differences; returns both one-sided p-values and the maximum.
    """
    from scipy.stats import t as t_dist

    diffs = _paired_differences(a, b, constant)
    n = diffs.size
    if n == 0:
        return {"n": 0, "p_tost": 1.0, "mean_diff": None}
    if n < 2:
        return {"n": n, "p_tost": 1.0, "mean_diff": float(diffs[0])}
    mean_diff = float(diffs.mean())
    sd = float(diffs.std(ddof=1))
    se = sd / math.sqrt(n)
    if se == 0:
        p_lower = 0.0 if mean_diff + delta > 0 else 1.0
        p_upper = 0.0 if mean_diff - delta < 0 else 1.0
    else:
        p_lower = float(t_dist.cdf((mean_diff - delta) / se, df=n - 1))
        p_upper = float(1 - t_dist.cdf((mean_diff + delta) / se, df=n - 1))
    return {
        "n": n,
        "mean_diff": mean_diff,
        "sd": sd,
        "delta": delta,
        "p_lower": p_lower,
        "p_upper": p_upper,
        "p_tost": max(p_lower, p_upper),
    }


def holm_bonferroni(p_values: Sequence[float]) -> tuple[float, ...]:
    """Holm-Bonferroni adjusted p-values (pure Python, no dependencies)."""
    n = len(p_values)
    if n == 0:
        return ()
    ordered = sorted((float(p), i) for i, p in enumerate(p_values))
    adjusted = [0.0] * n
    previous = 0.0
    for rank, (p, original_index) in enumerate(ordered, start=1):
        candidate = p * (n - rank + 1)
        adjusted[original_index] = previous = max(previous, min(candidate, 1.0))
    return tuple(adjusted)