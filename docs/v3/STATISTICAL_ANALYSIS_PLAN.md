# Statistical Analysis Plan

**Status**: FROZEN (Gate 3, 2026-08-05)

## Analysis Population

- **Intent-to-execute**: All registered pairs, conditions, and repetitions.
- **Per-protocol**: Excludes timeout, infrastructure failure, and route-drift exclusions.
- **Missing data**: Missing at random (MAR) assumed; no imputation for primary analysis.

## Primary Analyses

### H1: Approved Signal Sensitivity

- **Test**: One-sided paired permutation test (AUR > 1.0).
- **Estimand**: AUR point estimate and 95% CI.
- **Decision**: AUR > 1.0 and lower bound > 1.0.

### H2: PSBE Authorized Utility Retention

- **Test**: One-sided confidence interval for AUR.
- **Estimand**: AUR point estimate and 95% lower bound.
- **Decision**: AUR ≥ 0.80 and 95% LB > 0.60.

### H4: Prohibited Influence Reduction

- **Test**: Paired permutation test (two-sided) with Holm adjustment.
- **Contrasts**: B0 vs P3, B1 vs P3, B2 vs P3.
- **Estimand**: UIR difference and 95% CI for each contrast.
- **Decision**: All Holm-adjusted p-values < 0.05.

## Secondary Analyses

### H3a: Noninferiority (B0 vs B2)

- **Test**: One-sided noninferiority test (margin 0.05).
- **Estimand**: Δacc (B0 − B2).
- **Decision**: Δacc ≥ −0.05.

### H3b: Equivalence (B0 vs B2)

- **Test**: Two one-sided tests (TOST) (margin 0.03).
- **Estimand**: UIR difference (B0 − B2).
- **Decision**: |UIR\_B0 − UIR\_B2| ≤ 0.03.

### H5: Cross-Layer Value

- **Test**: Paired permutation test (one-sided).
- **Estimand**: Δsilent (B2 − P3).
- **Decision**: Δsilent ≥ 0.20.

### H6: Layer Monotonicity

- **Test**: Ordered contrasts (P0 vs P1, P1 vs P2, P2 vs P3).
- **Estimand**: Δsilent for each adjacent pair.
- **Decision**: Δsilent ≤ 0 for all pairs AND Δsilent < 0 in ≥ 2 families.

### H7: Reconstructable Evidence

- **Test**: One-sided proportion test.
- **Estimand**: EVC point estimate and 95% lower bound.
- **Decision**: EVC ≥ 0.95.

### H8: Authorized Availability

- **Test**: One-sided noninferiority test (margin 0.10).
- **Estimand**: Δavail (P3 − B2).
- **Decision**: Δavail ≥ −0.10.

### H9: DP Empirical Leakage Reduction

- **Test**: Wilcoxon signed-rank test on composite privacy-risk rank.
- **Estimand**: Rank difference (D0 − D2).
- **Decision**: rank\_D2 < rank\_D0 AND Δacc ≤ 0.10.

### H10: Budget Enforcement

- **Test**: Exact binomial test.
- **Estimand**: Proportion of budget attacks prevented or failed closed.
- **Decision**: Proportion = 1.0.

## Multiple Comparisons Strategy

- **Primary family**: H1, H2, H4 (3 tests).
- **Adjustment**: Holm step-down within primary family.
- **Secondary family**: H3a, H3b, H5–H10 (reported but not adjusted).
- **Reporting**: Adjusted p-values for primary; unadjusted for secondary.

## Sensitivity Analyses

- **Trimmed AUR**: 1st–99th percentile trimming.
- **Model-stratified**: Per-model estimates for H1, H2, H4.
- **Dataset-stratified**: Per-dataset estimates for all hypotheses.
- **Robustness**: Bootstrap 95% CIs (10,000 resamples).

## Software

- **Language**: Python 3.12+.
- **Permutation tests**: `scipy.stats.permutation_test`.
- **Bootstrap**: `scipy.stats.bootstrap`.
- **Holm adjustment**: `statsmodels.stats.multitest.multipletests`.
- **Reproducibility**: All random seeds set; version-locked dependencies.
