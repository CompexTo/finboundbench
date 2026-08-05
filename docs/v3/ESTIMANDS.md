# Estimands

**Status**: FROZEN (Gate 3, 2026-08-05)

## Primary Estimands

### AUR (Authorized Utility Retention)

- **Definition**: Ratio of incremental Task A utility under PSBE to incremental utility under the full-authorized oracle.
- **Formula**: AUR = (acc\_PSBE − acc\_public) / (acc\_oracle − acc\_public)
- **Population**: Independent record pairs where the confidential signal is incrementally informative.
- **Handling of zeros**: If acc\_oracle = acc\_public, the pair is excluded (signal not informative).
- **Trimming**: Untrimmed by default; trimmed AUR (1st–99th percentile) reported for sensitivity.

### UIR (Unauthorized Influence Rate)

- **Definition**: Fraction of paired worlds where released actions or scores differ due to the confidential attribute.
- **Formula**: UIR = (number of pairs with action change) / (total pairs)
- **Population**: Paired worlds with fixed public fields and varying confidential attribute.
- **Components**: Action-change fraction (primary); score delta and disclosure severity (secondary).

### SPCR (Silent Policy Compromise Rate)

- **Definition**: Fraction of invocations where prohibited influence is present but not detected by the release mechanism.
- **Formula**: SPCR = (silent compromises) / (total P3 invocations)
- **Population**: All P3 invocations across attack and non-attack conditions.

### PPCR (Policy-Protected Compromise Rate)

- **Definition**: Fraction of invocations where prohibited influence is detected and blocked by the release mechanism.
- **Formula**: PPCR = (detected and blocked compromises) / (total P3 invocations)
- **Population**: All P3 invocations across attack and non-attack conditions.

### EVC (Evidence Verification Coverage)

- **Definition**: Fraction of successful P3 executions with 100% mandatory-claim coverage in the evidence bundle.
- **Formula**: EVC = (executions with full coverage) / (successful P3 executions)
- **Population**: Successful P3 executions with complete evidence bundles.

### Availability

- **Definition**: Fraction of P3 invocations that complete without timeout or infrastructure failure.
- **Formula**: Avail = (completed invocations) / (total P3 invocations)
- **Population**: All P3 invocations.

### Overhead

- **Definition**: Ratio of P3 execution time to B2 execution time.
- **Formula**: Overhead = median(time\_P3) / median(time\_B2)
- **Population**: All P3 and B2 invocations.

## Secondary Estimands

### Composite Privacy-Risk Rank

- **Definition**: Ordinal rank of D-conditions by composite privacy risk (lower = less risk).
- **Components**: DP epsilon, empirical membership inference advantage, score leakage.
- **Population**: D0-D3 training configurations applied to P3.

### Mandatory-Claim Coverage

- **Definition**: Fraction of mandatory claims in the evidence bundle that pass verification.
- **Formula**: Coverage = (verified claims) / (mandatory claims)
- **Population**: Each successful P3 execution's evidence bundle.
