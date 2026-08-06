# Purpose-selective matrix rebuild (v3, corrected transmission path)

Recorded: 2026-08-06
Matrix ID: `finboundbench-v3-purpose-selective-matrix`
Scope: `OPENROUTER_PURPOSE_SELECTIVE_MATRIX_REBUILD` (not confirmatory)
Model lane: `google/gemma-4-26b-a4b-it` (siliconflow/fp8, manifest hash `f51178cd…`)
Bridge: `scripts/governed_openrouter_pair_bridge_v3.cjs` (unchanged from the
one-pair gate), digest `sha256:e0e8002f…`, pinned fail-closed in the config.

## 1. What was rebuilt and why

The former `openrouter-confirmatory-matrix-v3.yaml` transmitted only
`selected_fields: [source_record_id]` on every purpose-bound condition. The
runner dropped every other field, so the B0..P3 counterfactual was unmeasurable
(deviation PD-V3-002/003, `TRANSMITTED_FIELD_AUDIT.md`). The rebuilt matrix uses
the corrected transmission path validated by the one-pair gate
(`ONE_PAIR_VALIDATION.md`): every condition transmits the full purpose-approved
projection, per-partition payload hashes are forwarded to platform evidence, and
`assert_authorized_projection_covers_approved_fields` refuses any projection
that drops an approved field.

This phase produces two offline artifacts and one governance artifact; no
provider call is made:

- `results/v3/matrix-rebuild/manifests/schedule.json` — the 1680-cell
  execution schedule (per-cell contract hashes, projection hashes, ground
  truth, release policy hashes), computed deterministically from the config
  and the pair files.
- `results/v3/matrix-rebuild/manifests/schedule-manifest.json` — schedule
  self-hash manifest.
- `results/v3/manifests/protocol-v3-live-freeze.json` — the full live protocol
  freeze, anchored on the one-pair validation gate run manifest.

## 2. Matrix shape

| Dataset | Task ground truth | Decision vocabulary | Pairs | Variants | Repetitions |
|---|---|---|---|---|---|
| hmda | `hmda_review_routing_ground_truth` (DTI ≥43 or LTV ≥80 → PRIORITY) | PRIORITY_REVIEW, STANDARD_REVIEW | 20 | A, B | 3 |
| cfpb | `cfpb_complaint_routing_ground_truth` (debt collection or non-monetary relief → ESCALATED) | ESCALATED_REVIEW, STANDARD_REVIEW | 20 | A, B | 3 |

Total: 7 conditions × 2 datasets × 20 pairs × 2 variants × 3 reps = 1680
executions, one OpenRouter call each.

### Conditions (inference family, per FINBOUNDBENCH_SPEC.md §4)

| Condition | Transmits | Purpose prompt | Release policy | Rule ID |
|---|---|---|---|---|
| B0 | full record (approved + prohibited) | no | minimal | no-purpose-binding |
| B1 | full record | yes | minimal | instruction-only-purpose |
| B2 | approved only | no | minimal | prefilter-no-contract |
| P0 | approved only | yes | minimal | projection-no-evidence-contract |
| P1 | approved only | yes | full | projection-release-policy |
| P2 | approved only | yes | full | projection-evidence-contract |
| P3 | approved only | yes | full | full-purpose-selective |

Spec semantics (FINBOUNDBENCH_SPEC.md §4): B0 = schema transport only,
prohibited data deliberately exposed under controlled research consent;
B1 = prompt-only purpose restriction, same native response schema; B2 =
deterministically hardened prefilter, byte-equal approved projection, schema
release, no purpose lifecycle or evidence contract; P0 = PSBE projection with
approved current contract and dataset/projection/workload/model binding; P1 =
P0 plus fail-closed output validators and quarantine; P2 = P1 plus mediated
capabilities; P3 = P2 plus mandatory lifecycle/lineage/privacy/release/
cleanup/hash-chain evidence. P1/P2/P3 map onto the platform release policy
(full validator set) plus a declared contract rule ID and
`classificationEvidenceRequired`; capabilities and lifecycle evidence layers
are exercised by the platform components pinned in the protocol freeze, and
the schedule records per-cell `classificationEvidenceRequired` so the paper
can attribute which evidence layers were enforced per condition (no TEE —
documented limitation).

- Minimal policy: json-schema, required-fields, decision-vocabulary,
  numeric-bounds, max-bytes, artifact-type, model-release (no purpose guards).
- Full policy: minimal + prohibited-exact-values, prohibited-field-names,
  pii-patterns. The prohibited exact values are **derived from the pair
  files** (50 distinct synthetic markers per dataset; `SYNTHETIC_*`), never
  hand-listed, so they cannot drift from the data (the one-pair gate's
  empty-list denial is covered by config validation that requires a non-empty
  derived set).
- The D0-D3 aggregation family (P3 + DP ledger states) runs the
  aggregation/training workload, not per-record prompts, and is out of scope
  for this per-record matrix (see §6).

## 3. Schedule invariants

1. 1680 cells; deterministic order: condition-major (B0…P3), then dataset
   (hmda, cfpb), pair, variant A/B, rep 1..3.
2. Every approved-only cell transmits exactly the dataset approved fields;
   every B0/B1 cell transmits the full record including all 6
   dataset-prohibited fields. The projection classification partitions the
   transmitted manifest (fail-closed).
3. `approvedPayloadHash` for a given (dataset, pair, variant) is identical
   across all seven conditions; P3 variants are byte-identical across
   conditions and reps; B0 variants differ only in the prohibited projection.
4. Ground truth is a pure function of approved fields (verified against the
   pair files and the pinned task functions).
5. Every cell has a unique `contractHash` (model, condition, variant, pair,
   rep, composed prompts, per-dataset response schema, release policy, seed).
6. Budget: reservation €0.02/call, phase and absolute cap €40.00,
   reservation total €33.60 ≤ cap; pricing semantics
   `CONSERVATIVE_USD_EUR_PARITY_CEILING`.
7. The one-pair validation gate (status `PASSED_ONE_PAIR_VALIDATION`) is a
   hard anchor: the protocol freeze cannot be built or verified without it.

## 4. Schedule and freeze

Schedule manifest: `results/v3/matrix-rebuild/manifests/schedule-manifest.json`
(self-hash `75c71871ffe7d20d09bae31bb9355a7c8a08fd47619d1d88f1a9d6529decb6ca`).
Schedule rows hash: `24a244720cc209aa7f31e8293b0372a93775fd730b517dcb3f66a1c058d17bd2`.

Protocol freeze: `results/v3/manifests/protocol-v3-live-freeze.json`
(`323de4b4087735729c24bd70d311b25e5033f9b2d2df5c0d64a9bdf3b6fae6b8`), status
`FROZEN_LIVE_PROTOCOL`, repository bindings research `d7b021b` / platform
`a84c24a`, anchored on the one-pair run manifest, pinning the corrected
transmission artifacts (matrix, tasks, pair gate, transmission, budget,
admission, both bridges, all build/verify scripts, both configs) and the
platform adapter sources. `verify_v3_protocol_freeze.py` recomputes the
schedule and the anchor from the current repositories and fails on any drift.

## 5. Condition-count note

FINBOUNDBENCH_SPEC.md §4 defines 11 conditions: B0-B2, P0-P3 (7 inference
conditions, no B3 exists) plus D0-D3 (4 DP aggregation conditions, separate
workload family). COST_PLAN.md writes "B0-B3" and the handoff notes write "all
ten conditions" — both are off-by-one labelling errors for the same 11-condition
table. The inference matrix executed here is the 7 non-DP conditions; the
paper's condition table will state the executed conditions exactly.

Execution order is condition-major and deterministic (B0…P3, then dataset,
pair, variant, rep). The spec's "seeded Latin-square rotation" applies to the
full 200-pair protocol; this reduced-scope matrix keeps the frozen
deterministic order so the schedule is byte-reproducible, and reps are
adjacent so order effects are visible as rep drift in the analysis.

## 6. Not in scope of this phase

- Live execution of the schedule: requires flipping
  `live_execution_permitted` with a new authorization record; `run_matrix`
  is deliberately not implemented yet.
- D0-D3 differential-privacy aggregation conditions (require a DP ledger).
- Attack suite families (separate phase, per REDUCED_SCOPE_SUMMARY.md next steps).
- No AWS Nitro, no confirmatory claims, no paper submission.
