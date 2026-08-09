# Result-statement registry

Status: **V4 CONFIRMATORY COMPLETE (2026-08-07 freeze; paper build 2026-08-09)**

Every sentence identifies a claim ID, hypothesis, estimand, population, effect
and uncertainty, raw manifest, analysis artifact, table/figure cell, and
limitation. The v4 section is the authoritative registry for the paper;
v3 rows are retained as the honest history the paper references.

## V4 confirmatory claims (paper-traceable)

| Claim ID | Permitted sentence | Hypothesis | Estimand | Population | Effect | Uncertainty | Raw manifest | Artifact | Paper cell | Limitation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V1 | Declaring purpose raised balanced accuracy from 0.32 (no purpose) to 0.71 on the primary study. | H1 | BACC A1 - A0 | 100 pairs, primary | +0.39 | 95% CI [0.21, 0.56], p 0.00020 | `results/v4/confirmatory/primary-window-2/…/events.jsonl` | `results/v4/statistics/primary-statistical-report.json` | Tab. 1; Fig. 1 | DeepSeek V4 Pro, hardship-support routing only |
| V2 | Governed execution retained the full authorized utility gain (AUR = 1.0). | H2 | (BACC A3 - A0)/(BACC A1 - A0) | 100 pairs, primary | AUR 1.0 | CI [1.0, 1.0] | primary events | primary report | Tab. 1; Fig. 1 | Same task/model pair |
| V3 | Prohibited-visible data changed the decision on every pair (UIR P0 = 1.00 vs floor 0.00). | H3 | UIR P0 - ND floor | 100 pairs, primary | 1.00 | CI [1.00, 1.00], McNemar p 1.58e-30 | primary events | primary report | Tab. 1 | One model/task pair |
| V4 | Masking suppressed prohibited influence exactly (UIR P2 = 0.00, P3 = 0.00). | H5/H6 | UIR P2/P3 vs P0, vs floor | 100 pairs, primary | -1.00 / -0.00 | p 0.0 | primary events | primary report | Tab. 1 | Narrow single-field masking |
| V5 | Replication (Kimi K3, fraud review): purpose gain 0.1083, AUR 1.0, UIR P0 0.9646 vs floor 0.0375, P2 0.00, P3 0.0083. | H1/H2/H3/H5/H6 | all metrics | 120 pairs, replication | see report | CIs [0.033,0.175] (H1), [0.8805,0.9646] (H3); McNemar p 3.94e-31 | `results/v4/confirmatory/replication-window-8/…/events.jsonl` | `results/v4/statistics/replication-statistical-report.json` | Tab. 2; Fig. 1 | 16 transient failures excluded per registered taxonomy; cost not frozen |
| V6 | Both studies passed every pre-registered gate; the effect reproduces across two model families and two financial tasks. | interpretation rule 1 | both chains | 2 studies | PASS x10 | n/a | both event files | `confirmatory-statistical-report.json` | Sec. 7.3 | Internal verification only |
| V7 | Every headline metric and both McNemar p-values were reproduced by an independent implementation (17/17 checks). | verification | recomputation | raw events | PASS | n/a | frozen events | `results/v4/evidence/confirmatory-verification-bundle.json` | Sec. 7.3 | Automated cross-check, not external audit |
| V8 | P2 and P3 were statistically equivalent (TOST) in both studies. | H7 | UIR P2 - P3 | both studies | 0.00 / -0.0083 | p_TOST 0.0 / 9.98e-07 | both event files | both reports | Tabs. 1-2; Sec. 7.4 | Deterministic masking and governed masking indistinguishable on one narrow field; no superiority claim |

## V3 diagnostic-phase claims (history; withdrawn protocol)

| Claim ID | Permitted sentence | Status |
| --- | --- | --- |
| A1 | Of five OpenRouter candidates, three passed the R0 schema-route-cost admission gate. | descriptive, v3 |
| A2 | Of 18 position-diagnostic invocations, 15 passed; gemma-4-26b failed layouts. | descriptive, v3 |
| A3 | Of 36 confirmatory invocations, 32 passed; all four denials were gemma-4-26b on CFPB. | descriptive, v3 |
| E1 | Test-double reduced-scope run: silent compromise 0.2426, availability 0.9857, AUR 0.9341. | INVALID for live claims — v3 withdrawn; v4 mandates live events |
| E2 | Test-double attack detection 75.7% (178/235). | not claimed in v4; attack suite out of scope |
| E3 | Test-double evidence coverage 20/20. | not claimed in v4 |
| M1-M5 | Live v3 matrix (3360 cells): release 0.886/0.831; UIR at/below floor NOT_CONFIRMATORY; taskB P0 availability 0.675. | NOT_CONFIRMATORY; motivates v4 eligibility gates |

## Claim discipline (paper-verbatim rules)

- Influence results are reported **relative to the measured ND floor**, never in
  absolute terms (allowed phrasing: "reduced to approximately the natural
  decision floor").
- No superiority claim of governed execution over masking (P2 ≈ P3).
- H4 (P1 < P0) is NOT TESTABLE in the confirmatory design — no claim exists.
- No TEE, formal non-interference, or training-data claims.
- Model-task results are per-lane; no cross-model pooling claims.
