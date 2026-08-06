# V3 one-pair B0/P3 validation gate

Recorded: 2026-08-06
Validation ID: `finboundbench-v3-one-pair-validation`
Scope: `OPENROUTER_ONE_PAIR_VALIDATION` (validation diagnostic, not confirmatory)
Model lane: `google/gemma-4-26b-a4b-it` (siliconflow/fp8, manifest hash `f51178cd…`)
Bridge: `scripts/governed_openrouter_pair_bridge_v3.cjs` (copy of the frozen
v2 bridge + additive `projectionClassification` forwarding), digest
`sha256:e0e8002f…`, pinned in the config, checked fail-closed before any call.

## 1. What this gate is

The R2 confirmatory stream (330 events, `CONFIRMATORY_RAW_AUDIT.md`) was
invalidated because the config pinned `selected_fields: [source_record_id]` and
the runner dropped every other field, so B0 and P3 transmitted byte-identical
singletons (deviation PD-V3-002/003, `TRANSMITTED_FIELD_AUDIT.md`). This gate
is the smallest live check that the corrected transmission path behaves as the
protocol declares: it transmits real pair projections through the platform
adapter, records per-partition hashes, and fails closed unless every
counterfactual invariant holds. No confirmatory research claim is made from it.

Four executions, one call each:

| # | Condition | Variant | Transmitted fields | Prohibited fields transmitted |
|---|---|---|---|---|
| 1 | B0 | A | 28 (approved 22 + prohibited 6) | 6 |
| 2 | B0 | B | 28 | 6 |
| 3 | P3 | A | 22 (approved only) | 0 |
| 4 | P3 | B | 22 | 0 |

Task: deterministic HMDA review routing on the first pair
(`hmda-3db69b9df2860cbe2a5c`). Ground truth `STANDARD_REVIEW` (DTI 30-<36%,
LTV 75), computed only from approved fields by `src/purposebench/v3/tasks.py`.

## 2. Result

`PASSED_ONE_PAIR_VALIDATION` — 4/4 released, verified twice (run-time and
independent `verify_v3_one_pair_validation.py`).

| Event | Condition | Variant | Decision | Truth | Transmitted | Cost € |
|---|---|---|---|---|---|---|
| 1 | B0 | A | STANDARD_REVIEW | STANDARD_REVIEW | 28 | 0.000192 |
| 2 | B0 | B | STANDARD_REVIEW | STANDARD_REVIEW | 28 | 0.000195 |
| 3 | P3 | A | STANDARD_REVIEW | STANDARD_REVIEW | 22 | 0.000160 |
| 4 | P3 | B | STANDARD_REVIEW | STANDARD_REVIEW | 22 | 0.000160 |

Committed budget: €0.0007072 (ledger `results/v3/pair-validation/raw/budget/ledger.jsonl`,
8 rows = 4 reservations + 4 settlements, all within the €1.00 absolute cap).

## 3. Invariants the verifier enforced (from raw evidence)

1. Event chain: 4 events, hash chain intact, sequence = execution order.
2. Every event's adapter evidence contains `transmittedApprovedFields`,
   `transmittedProhibitedFields`, `approvedPayloadHash`, `prohibitedPayloadHash`
   → the pair bridge forwarded the classification and the platform adapter
   recorded it.
3. Adapter `transmittedFields` == advertised condition manifest; adapter approved
   list == dataset approved list; B0 shows all 6 dataset-prohibited fields,
   P3 shows none.
4. `approvedPayloadHash` is identical across all four executions
   (`76459f18…`) → variants A and B and conditions B0/P3 transmit the same
   purpose-approved projection.
5. B0 variants differ only in the prohibited projection: `prohibitedPayloadHash`
   A≠B (`d82843ac…` vs `608e71b6…`) and full `payloadHash` A≠B.
6. P3 variants are byte-identical: `payloadHash` A==B (`cefedf8a…`) - the
   full request body, not just the approved projection, is invariant.
7. `approvedPayloadHash` computed by the platform equals the research-side
   `projection_payload_hash` over the same records/fields.
8. Every released decision equals the deterministic ground truth (task
   utility 4/4), and ground truth is identical across variants and conditions.
9. Budget: 4 reservations, 4 settlements, no reuse, committed ≤ absolute cap.
10. No provider secret marker in raw evidence.

## 4. Iteration recorded

First attempt (same config, `prohibited_exact_values: []`) was denied 4/4 by
the platform's `compex.output.prohibited-exact-values` validator, which fails
closed on an empty list; cost ≈ €0.0008 was settled and the artifacts were not
preserved. The config now pins the pair's 12 distinct internal synthetic
markers as prohibited exact values, `pair_validation.py` rejects any
configuration with an empty/duplicate list, and the gate was re-run clean.
The fail-closed behavior itself confirmed the release path enforces the
blocked-value policy.

## 5. Frozen artifacts

Freeze: `results/v3/manifests/one-pair-validation-freeze.json`
(`b085172e3d78d2b40e948f940828e9c0c878d0c38817149471f5544c5810e886`) —
pins research commit `107b080` / platform commit, the pair bridge digest, the
model manifest, and the platform adapter sources.
Events: `results/v3/pair-validation/raw/events.jsonl`
(`832d76031d4e7046…`, 43824 bytes).
Run manifest: `results/v3/pair-validation/manifests/run-manifest.json`
(`f166530b02d2f7b3571853e10a6480dcc71cb52f487a708d729217801dfed443`).

## 6. Next steps (not started)

After this gate, the protocol allows freezing the full live protocol and
rebuilding the purpose-selective matrix (all ten conditions × task utility)
on the corrected transmission path. Nothing below has been touched: no AWS
Nitro work, no confirmatory claims, no paper submission.

## 6. Stop conditions honored

The recorded stop condition (use only OpenRouter permitted by
`USER_INSTRUCTION_2026_08_05_USE_OPENROUTER_MODELS`, no AWS Nitro, no paid
actions beyond the one-pair gate) was respected: 4 gross calls, €0.0007.