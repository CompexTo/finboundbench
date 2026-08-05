# Power Analysis

**Status**: FROZEN (Gate 3, 2026-08-05)

## Design Parameters

- **Sample size**: 100 independent record pairs per dataset (HMDA + CFPB = 200 total).
- **Repetitions**: 3 repetitions per pair per condition.
- **Models**: 3 admitted models (kimi-k3, deepseek-v4-pro, gemma-4-26b).
- **Conditions**: B0, B1, B2, P0, P1, P2, P3, D0, D1, D2, D3.

## Power Calculation for H4 (UIR Reduction)

### Conservative Paired Scenario

- **Effect size**: 10-point UIR reduction (0.15 → 0.05).
- **Test**: Paired permutation test (two-sided).
- **Significance level**: α = 0.05 (Holm-adjusted for 3 primary contrasts).
- **Power**: 86.1% at the first Holm threshold.
- **Assumptions**: Paired differences are approximately symmetric; no clustering.

### Why 86.1%

The conservative paired planning scenario assumes:
- 100 independent pairs per dataset.
- Paired permutation test with 10,000 Monte Carlo samples.
- Holm adjustment for 3 primary contrasts (B0 vs P3, B1 vs P3, B2 vs P3).
- 10-point absolute UIR reduction as the minimum detectable effect.

This yields 86.1% power at the first Holm threshold (α = 0.05 / 3 = 0.0167).

### Sensitivity Analysis

| Effect Size | Power (n=100) | Power (n=200) |
|-------------|---------------|---------------|
| 5-point UIR reduction | 52% | 78% |
| 10-point UIR reduction | 86% | 97% |
| 15-point UIR reduction | 96% | >99% |

## Power for H2 (AUR Retention)

- **Effect size**: AUR = 0.80 (80% retention).
- **Lower bound**: 95% LB > 0.60.
- **Test**: One-sided confidence interval.
- **Power**: > 90% assuming AUR variance ≈ 0.01.

## Power for H5 (Compromise Reduction)

- **Effect size**: 20-point absolute reduction in silent compromise rate.
- **Test**: Paired permutation test.
- **Power**: > 85% assuming compromise rate variance ≈ 0.02.

## Multiple Comparisons

- **Primary family**: H1, H2, H4 (3 tests).
- **Adjustment**: Holm step-down.
- **Per-comparison α**: 0.05 / 3 = 0.0167 at first step.

## Sample Size Justification

100 pairs per dataset provides:
- Sufficient power for 10-point UIR reduction (86%).
- Sufficient power for AUR retention (90%).
- Practical budget constraints (200 pairs × 3 reps × 11 conditions × 3 models = 19,800 invocations).

## Budget Implications

At observed OpenRouter costs (~€0.03–0.05 per invocation):
- **Estimated total cost**: 19,800 × €0.04 = €792.
- **Budget ceiling**: €1,000 (conservative).
- **Contingency**: 20% for retries, failures, and route drift.
