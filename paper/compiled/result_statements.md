# Result-statement registry

Status: DIAGNOSTIC PHASE COMPLETE (2026-08-05)

Every sentence identifies a claim ID, hypothesis, estimand, population,
numerator/denominator, effect and uncertainty, raw manifest, analysis artifact,
table/figure cell, and limitation.

## Diagnostic-phase claims (R0/R1/R2)

| Claim ID | Permitted sentence | Hypothesis | Estimand | Population | Numerator/Denominator | Effect | Uncertainty | Raw manifest | Artifact | Table | Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | Of five OpenRouter candidates, three passed the R0 schema-route-cost admission gate. Two were excluded due to upstream route instability between captures. | R0 gate validation | Admission pass rate | 5 candidates | 3/5 | 0.60 | descriptive only | `results/v3/openrouter-admission/raw/events.jsonl` | `docs/v3/OPENROUTER_ADMISSION.md` | Tab. 1 | Route instability is model-specific; different captures may yield different outcomes. |
| A2 | Of 18 position-diagnostic invocations across six batch layouts, 15 passed and 3 were release-denied. Two of three models (kimi-k3, deepseek-v4-pro) passed all six layouts. | R1 layout robustness | Layout pass rate | 18 invocations | 15/18 | 0.83 | descriptive only | `results/v3/position-diagnostic/raw/events.jsonl` | `docs/v3/OPENROUTER_ADMISSION.md` | Tab. 2 | gemma-4-26b release denials are model-specific; layout sensitivity is not a system-level failure. |
| A3 | Of 36 confirmatory invocations across two datasets, two conditions, and three repetitions, 32 passed and 4 were release-denied. All four denials occurred for gemma-4-26b on the CFPB dataset. | R2 confirmatory execution | Confirmatory pass rate | 36 invocations | 32/36 | 0.89 | descriptive only | `results/v3/confirmatory-matrix/raw/events.jsonl` | `docs/v3/OPENROUTER_ADMISSION.md` | Tab. 3--4 | Full 200-pair confirmatory run with statistical inference is required for H1--H9 claims. |

## Pending confirmatory claims (require full 200-pair run)

| Claim ID | Permitted sentence | Hypothesis | Status |
| --- | --- | --- | --- |
| H1 | The full authorized oracle improves Task A balanced accuracy over public-only by at least 0.08. | Approved signal sensitivity | NOT\_YET\_TESTED |
| H2 | Full PSBE (P3) retains at least 80% of the oracle's incremental Task A utility: AUR >= 0.80, 95% LB > 0.60. | PSBE authorized utility retention | NOT\_YET\_TESTED |
| H3a | P0 is noninferior to B2 in task balanced accuracy with margin 0.05. | Honest-case filtering noninferiority | NOT\_YET\_TESTED |
| H3b | P0 is equivalent to B2 in UIR within 0.03 margin. | No projection magic | NOT\_YET\_TESTED |
| H4 | P3 has lower Task B UIR than B0 and B1, Holm-adjusted p < 0.05. | Prohibited influence reduction | NOT\_YET\_TESTED |
| H5 | P3 reduces silent policy compromise relative to B2 by >= 0.20 absolute. | Cross-layer value beyond prefiltering | NOT\_YET\_TESTED |
| H6 | Adding P0--P3 layers does not increase silent compromise and reduces it in >= 2 families. | Layer monotonicity | NOT\_YET\_TESTED |
| H7 | >= 0.95 of successful P3 executions have 100% mandatory-claim coverage. | Reconstructable evidence | NOT\_YET\_TESTED |
| H8 | P3 availability is noninferior to B2 with margin 0.10. | Authorized availability | NOT\_YET\_TESTED |
| H9 | D2 reduces composite privacy-risk rank without decreasing balanced accuracy by > 0.10. | DP empirical leakage reduction | NOT\_YET\_TESTED |
| H10 | Every budget attack attempt is prevented or fails closed. | Budget enforcement | NOT\_YET\_TESTED |
