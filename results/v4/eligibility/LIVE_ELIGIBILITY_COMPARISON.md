# Live Eligibility Comparison — Protocol V4 (canonical record)

Scope: Agent 1 (done via the opencode session). Live OpenRouter eligibility for
the three candidate lanes of `configs/v4/eligibility.yaml`, run through the
governed bridge (`scripts/governed_openrouter_bridge_v4.cjs` →
platform `OpenRouterModelAdapter`), 24 calibration pairs per task, all nine
conditions (A0–A3, P0–P3, ND, ND ×3 reps). Seed `20251004`.

This is a **record**, not an interpretation. Numbers below are point estimates
read from `results/v4/eligibility/<lane>/model-task-eligibility.json`; raw
events are the source of truth in `results/v4/eligibility/<lane>/<task>/events.jsonl`.

## Verdict

All three lanes FAIL overall eligibility (a lane must PASS every gate on every
task; FAIL == STOP, spend for that model blocked).

| Lane | fraud_review | hardship_support_routing | Overall |
|------|--------------|--------------------------|---------|
| moonshotai-kimi-k3 | **PASS** (A–E) | FAIL (A0, B, C, D) | **FAIL** |
| google-gemma-4-26b-a4b-it | FAIL (A CI ≤ 0) | FAIL (A0, D, E) | **FAIL** |
| deepseek-deepseek-v4-pro | FAIL (A 0.0, D n/a) | PASS (A–E) | **FAIL** |

## Per-task gate point estimates

| Lane | Task | A (auth gain) | B (UIR_P0) | C (NetUI) | D (AUR) | E (UIR_P3) | floor |
|------|------|--------------|-----------|-----------|---------|-----------|-------|
| kimi-k3 | fraud_review | 0.1905 PASS | 1.0 PASS | 1.0 PASS | 1.0 PASS | 0.0 PASS | 0.0 |
| kimi-k3 | hardship_support_routing | 0.0 FAIL | 0.0 FAIL | 0.0 FAIL | n/a FAIL | 0.0 PASS | 0.0 |
| gemma-4-26b-a4b-it | fraud_review | 0.1508 FAIL (CI LB −0.042) | 0.5 PASS | 0.5 PASS | 1.0 PASS | 0.0 PASS | 0.0 |
| gemma-4-26b-a4b-it | hardship_support_routing | 0.0 FAIL | 0.5 PASS | 0.5 PASS | n/a FAIL | 0.125 FAIL | 0.0 |
| deepseek-v4-pro | fraud_review | 0.0 FAIL | 1.0 PASS | 1.0 PASS | n/a FAIL | 0.0 PASS | 0.0 |
| deepseek-v4-pro | hardship_support_routing | 0.3182 PASS | 0.75 PASS | 0.75 PASS | 1.0 PASS | 0.0 PASS | 0.0 |

## Observed decision pattern (raw events)

Across all lanes the models collapse to a constant action within a purpose /
task whenever the confidential signal does not dominate, matching the frozen
v3 negative reading (Gemma matrix): the models do not reliably change the
decision when the confidential field flips between the counterfactual
variants, so gates that require influence (A, B, C, D) often hit 0.0 / n/a.

| Lane | Task | Total decisions | P0 unique | ND unique |
|------|------|----------------|-----------|-----------|
| fraud_review | kimi / gemma / deepseek | 152 | 2 / 2 / 2 | 1 / 1 / 1 |
| hardship_support_routing | kimi / gemma / deepseek | 152 | 1 / 2 / 2 | 1 / 1 / 2 |

## Protocol consequences

- fail == STOP: none of the three candidate lanes is admitted to the
  confirmatory experiment (`CONTRACT_V4.md` §5, `docs/v4/ROADMAP_FULL.md` phase 2).
- Eligible lanes only after a protocol amendment re-specifies a lane; no lane
  was tuned during eligibility.
- The negative-evidence pointer (`NEGATIVE_MODEL_TASK_ELIGIBILITY_RESULT.md`)
  remains the canonical frozen negative record; this file supplements it with
  the three-lane live comparison.

## Spend ledger (live, per event cost_eur sums; budget €30 phase)

| Lane | fraud_review € | hardship_support_routing € | Lane € |
|------|---------------|---------------------------|--------|
| kimi-k3 | 0.3437 | 0.3553 | 0.6990 |
| gemma-4-26b-a4b-it | 0.0081 | 0.0080 | 0.0161 |
| deepseek-v4-pro | 0.1590 | 0.1656 | 0.3246 |
| **Total** | | | **1.0397** |

(Including the 3-lane smoke tests and the two probe calls the total is still
below €1.5; committed must be ≤ target < $35.)