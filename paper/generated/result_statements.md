# Result-statement registry

Status: EXPERIMENTAL PHASE COMPLETE (2026-08-05)

Every sentence identifies a claim ID, hypothesis, estimand, population,
numerator/denominator, effect and uncertainty, raw manifest, analysis artifact,
table/figure cell, and limitation.

## Diagnostic-phase claims (R0/R1/R2)

| Claim ID | Permitted sentence | Hypothesis | Estimand | Population | Numerator/Denominator | Effect | Uncertainty | Raw manifest | Artifact | Table | Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | Of five OpenRouter candidates, three passed the R0 schema-route-cost admission gate. Two were excluded due to upstream route instability between captures. | R0 gate validation | Admission pass rate | 5 candidates | 3/5 | 0.60 | descriptive only | `results/v3/openrouter-admission/raw/events.jsonl` | `docs/v3/OPENROUTER_ADMISSION.md` | Tab. 1 | Route instability observed in these captures; different captures may yield different outcomes. |
| A2 | Of 18 position-diagnostic invocations across six batch layouts, 15 passed and 3 were release-denied. Two of three models (kimi-k3, deepseek-v4-pro) passed all six layouts. | R1 layout robustness | Layout pass rate | 18 invocations | 15/18 | 0.83 | descriptive only | `results/v3/position-diagnostic/raw/events.jsonl` | `docs/v3/OPENROUTER_ADMISSION.md` | Tab. 2 | Release denials observed for gemma-4-26b; layout sensitivity may be model-specific. |
| A3 | Of 36 confirmatory invocations across two datasets, two conditions, and three repetitions, 32 passed and 4 were release-denied. All four denials occurred for gemma-4-26b on the CFPB dataset. | R2 confirmatory execution | Confirmatory pass rate | 36 invocations | 32/36 | 0.89 | descriptive only | `results/v3/confirmatory-matrix/raw/events.jsonl` | `docs/v3/OPENROUTER_ADMISSION.md` | Tab. 3--4 | Full 200-pair confirmatory run with statistical inference required for H1--H10 claims. |

## Experimental-phase claims (reduced-scope confirmatory)

| Claim ID | Permitted sentence | Hypothesis | Estimand | Population | Numerator/Denominator | Effect | Uncertainty | Raw manifest | Artifact | Table | Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | Of 330 confirmatory invocations with gemma-4-26b, 263 passed and 66 were release-denied. | Reduced-scope confirmatory execution | Confirmatory pass rate | 330 invocations | 263/330 | 0.797 | descriptive only | `results/v3/confirmatory-reduced/raw/events.jsonl` | `results/v3/statistical-analysis/derived/statistical-report.json` | Tab. 5 | Test-double oracle; live execution required for definitive claims. |
| E2 | Attack detection rate is 75.7% across 235 test-double attacks. | Attack detection | Detection rate | 235 attacks | 178/235 | 0.757 | descriptive only | `results/v3/attack-suite/raw/events.jsonl` | `results/v3/statistical-analysis/derived/statistical-report.json` | Tab. 6 | Test-double oracle; live attack execution required. |
| E3 | Evidence verification coverage is 100% across 20 test-double executions. | Evidence coverage | Coverage rate | 20 executions | 20/20 | 1.000 | descriptive only | `results/v3/evidence-verification/raw/events.jsonl` | `results/v3/statistical-analysis/derived/statistical-report.json` | Tab. 6 | Test-double oracle; live evidence verification required. |

## Live purpose-selective matrix claims (NOT_CONFIRMATORY)

| Claim ID | Permitted sentence | Estimand | Population | Numerator/Denominator | Effect | Uncertainty | Raw manifest | Artifact | Table | Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M1 | The live matrix released 1489/1680 cells on task A and 1396/1680 on task B over the OpenRouter lane. | Release rate | 3360 cells, two tasks | 1489/1680, 1396/1680 | 0.886, 0.831 | Wilson 95% per condition | `results/v3/matrix-rebuild/{,taskB}/raw/events.jsonl` | `matrix-analysis.json` | Tab. 1 | One lane; NOT_CONFIRMATORY. |
| M2 | Conformant balanced accuracy is B0 0.656, B2 0.494, P3 0.401 on taskA; B0 0.500, B2 0.561, P3 0.577 on taskB. | Balanced accuracy | Released cells per condition | policy-conformant counts | see text | descriptive | `results/v3/matrix-rebuild/raw/events.jsonl` | `matrix-analysis.json` | Tab. 8 | NOT_CONFIRMATORY. |
| M3 | The oracle denominator is +0.162 (taskA, gate passes) and -0.061 (taskB, gate fails); where defined, PSBE retention is negative (P3 -0.575). | AUR | task-condition cells | (U_PSB) | see text | gate-based | `results/v3/matrix-rebuild/raw/events.jsonl` | `matrix-analysis.json` | Tab. 9 | Gate dependence; no inferential claim. |
| M4 | Full-record UIR is at or below the approved-only nondeterminism floor for both tasks; no unauthorized influence detected. | UIR vs floor | valid counterfactual pairs | changed/total | see text | Wilson 95% | `results/v3/matrix-rebuild/raw/events.jsonl` | `matrix-analysis.json` | Tab. 10 | Not separable from nondeterminism at these sample sizes. |
| M5 | P2/P3 release 100% in both tasks; taskB P0 fails 78/240 (availability 0.675). | Availability | 240 cells per condition per task | released/attempted | see text | Wilson 95% | `results/v3/matrix-rebuild/{,taskB}/raw/events.jsonl` | `matrix-analysis.json` | Tab. 11 | One lane. |

## Pending confirmatory claims (require the completed statistical-analysis phase)

| Claim ID | Permitted sentence | Hypothesis | Estimand | Population | Numerator/Denominator | Effect | Uncertainty | Raw manifest | Artifact | Table | Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H1 | The full authorized oracle improves Task A balanced accuracy over public-only by at least 0.08. | AUR delta | D-pair utility | confirmatory pairs | marginal utility | non-informative until statistical report | pending | `results/v3/matrix-rebuild/raw/events.jsonl` | pending stat report | pending | Needs completed statistical analysis |
| H2 | Full PSBE (P3) retains at least 80% of the oracle's incremental Task A utility: AUR >= 0.80, 95% LB > 0.60. | AUR | P3 vs baseline | confirmatory pairs | AUR | CI bounds pending | pending stat | `results/v3/matrix-rebuild/raw/events.jsonl` | pending | pending | Needs completed statistical analysis |
| H3a | P0 is noninferior to B2 in task balanced accuracy with margin 0.05. | Accuracy margin | B2 vs P0 | confirmatory pairs | delta acc | CI pending | pending | `results/v3/matrix-rebuild/…` | pending | pending | Needs completed statistical analysis |
| H3b | P0 is equivalent to B2 in UIR within 0.03 margin. | UIR equivalence | B2 vs P0 | confirmatory pairs | UIR | CI pending | pending | `results/v3/…` | pending | pending | Needs completed statistical phase |
| H4 | P3 has lower Task B UIR than B0 and B1, Holm-adjusted p < 0.05. | UIR | influence reduction | valid pairs | UIR difference | p-value pending | pending | `results/v3/…` | pending | pending | Needs completed statistical phase |
| H5 | P3 reduces silent policy compromise relative to B2 by >= 0.20 absolute. | Compromise | attack suite + matrix | confirmation | delta | CI pending | pending | `results/v3/…` | pending | pending | Live attack execution required |
| H6 | Adding P0--P3 layers does not increase silent compromise and reduces it in >= 2 families. | Layering | monotonic | confirmation | delta | CI pending | pending | `results/v3/…` | pending | pending | Live attack execution required |
| H7 | >= 0.95 of successful P3 executions have 100% mandatory-claim coverage. | Evidence | coverage | live P3 executions | coverage | CI pending | pending | `results/v3/…` | pending | pending | Independent verification required |
| H8 | P3 availability is noninferior to B2 with margin 0.10. | Availability | P3 vs B2 | live attempts | rely | CI pending | pending | `results/v3/…` | pending | pending | Needs completed statistical phase |
| H9 | D2 reduces composite privacy-risk rank without decreasing balanced accuracy by > 0.10. | DP leakage | D-layer | DP runs | rank | CI pending | pending | `results/v3/…` | pending | pending | DP-SGD completion required |
| H10 | Every budget attack attempt is prevented or fails closed. | Budget | exhaustion | attack | rate | CI pending | pending | `results/v3/…` | pending | pending | Live attack execution required |
