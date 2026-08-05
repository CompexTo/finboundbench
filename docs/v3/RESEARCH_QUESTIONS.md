# Research Questions

**Status**: FROZEN (Gate 3, 2026-08-05)

## RQ1 (Primary — Authorized Utility)

**Question**: Does a confidential attribute improve an approved financial task when the runtime is authorized to use it?

**Estimand**: Authorized Utility Retention (AUR) — ratio of incremental utility under full PSBE relative to the full-authorized oracle.

**Population**: Independent record pairs drawn from HMDA and CFPB public datasets with semi-synthetic confidential signals.

**Decision rule**: PSBE (P3) retains at least 80% of the oracle's incremental Task A utility (AUR ≥ 0.80, 95% lower bound > 0.60).

## RQ2 (Primary — Unauthorized Influence)

**Question**: Does a confidential attribute influence a prohibited financial task when the runtime is authorized to suppress it?

**Estimand**: Unauthorized Influence Rate (UIR) — fraction of paired worlds where released actions or scores differ due to the confidential attribute.

**Population**: Same paired worlds as RQ1, evaluated on prohibited Task B.

**Decision rule**: P3 has lower Task B UIR than B0 and B1, Holm-adjusted p < 0.05.

## RQ3 (Boundary Integrity)

**Question**: Does deterministic prefiltering (B2) provide comparable authorized utility and superior unauthorized influence suppression relative to prompt-only (B1)?

**Estimand**: Noninferiority of B0 vs B2 in Task A balanced accuracy (margin 0.05); equivalence of B0 vs B2 in UIR (margin 0.03).

**Population**: Same paired worlds as RQ1/RQ2.

**Decision rule**: B0 is noninferior to B2 in accuracy; B0 is equivalent to B2 in UIR.

## RQ4 (Output Release)

**Question**: Does the PSBE release mechanism prevent silent policy compromise?

**Estimand**: Absolute reduction in silent policy compromise rate relative to B2.

**Population**: All P3 invocations across attack and non-attack conditions.

**Decision rule**: P3 reduces silent compromise relative to B2 by ≥ 0.20 absolute.

## RQ5 (Differential Privacy)

**Question**: Does DP-SGD training reduce empirical privacy risk without degrading authorized utility?

**Estimand**: Composite privacy-risk rank across D-conditions.

**Population**: D0-D3 training configurations applied to P3.

**Decision rule**: D2 reduces composite privacy-risk rank without decreasing balanced accuracy by > 0.10.

## RQ6 (Evidence & Availability)

**Question**: Does PSBE maintain reconstructable evidence and authorized availability?

**Estimand**: Mandatory-claim coverage fraction (H7); noninferiority of P3 availability vs B2 (H8).

**Population**: Successful P3 executions with complete evidence bundles.

**Decision rule**: ≥ 0.95 of successful P3 executions have 100% mandatory-claim coverage; P3 availability noninferior to B2 (margin 0.10).

## RQ7 (Budget Enforcement)

**Question**: Does the budget mechanism prevent over-debit attacks?

**Estimand**: Fraction of budget attack attempts that are prevented or fail closed.

**Population**: Registered budget attack variants.

**Decision rule**: Every budget attack attempt is prevented or fails closed (H10).
