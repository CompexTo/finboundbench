# Hypotheses

**Status**: FROZEN (Gate 3, 2026-08-05)

## Hypothesis Family: Diagnostic (A1–A3)

| ID | Statement | Status |
|----|-----------|--------|
| A1 | Of five OpenRouter candidates, three pass the R0 schema-route-cost admission gate. | SUPPORTED (3/5) |
| A2 | Of 18 position-diagnostic invocations across six batch layouts, ≥ 80% pass. | SUPPORTED (15/18 = 83%) |
| A3 | Of 36 confirmatory invocations across two datasets, two conditions, and three reps, ≥ 85% pass. | SUPPORTED (32/36 = 89%) |

## Hypothesis Family: Confirmatory (H1–H10)

| ID | Statement | Estimand | Decision Rule | Status |
|----|-----------|----------|---------------|--------|
| H1 | Full authorized oracle improves Task A balanced accuracy over public-only by ≥ 0.08. | AUR delta | AUR > 1.0, Δacc ≥ 0.08 | NOT\_YET\_TESTED |
| H2 | Full PSBE (P3) retains ≥ 80% of oracle's incremental Task A utility. | AUR | AUR ≥ 0.80, 95% LB > 0.60 | NOT\_YET\_TESTED |
| H3a | P0 is noninferior to B2 in Task A balanced accuracy (margin 0.05). | Accuracy margin | Δacc ≥ −0.05 | NOT\_YET\_TESTED |
| H3b | P0 is equivalent to B2 in UIR (margin 0.03). | UIR equivalence | \|UIR\_P0 − UIR\_B2\| ≤ 0.03 | NOT\_YET\_TESTED |
| H4 | P3 has lower Task B UIR than B0 and B1, Holm-adjusted p < 0.05. | UIR | UIR\_P3 < UIR\_B0, UIR\_P3 < UIR\_B1 | NOT\_YET\_TESTED |
| H5 | P3 reduces silent policy compromise relative to B2 by ≥ 0.20 absolute. | Compromise reduction | Δsilent ≥ 0.20 | NOT\_YET\_TESTED |
| H6 | Adding P0–P3 layers does not increase silent compromise and reduces it in ≥ 2 families. | Layer monotonicity | Δsilent ≤ 0 for all adjacent pairs | NOT\_YET\_TESTED |
| H7 | ≥ 0.95 of successful P3 executions have 100% mandatory-claim coverage. | Bundle verification | coverage ≥ 0.95 | NOT\_YET\_TESTED |
| H8 | P3 availability is noninferior to B2 (margin 0.10). | Availability | Δavail ≥ −0.10 | NOT\_YET\_TESTED |
| H9 | D2 reduces composite privacy-risk rank without decreasing balanced accuracy by > 0.10. | DP leakage reduction | rank\_D2 < rank\_D0, Δacc ≤ 0.10 | NOT\_YET\_TESTED |
| H10 | Every budget attack attempt is prevented or fails closed. | Budget enforcement | 100% prevention/fail-closed | NOT\_YET\_TESTED |
