# Purpose-selective matrix rebuild (v3, corrected transmission path)

Recorded: 2026-08-06
Matrix IDs: `finboundbench-v3-purpose-selective-matrix` (taskA),
`finboundbench-v3-purpose-selective-matrix-taskb` (taskB)
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

- `results/v3/matrix-rebuild/manifests/schedule.json` — the 1680-cell taskA
  execution schedule (per-cell contract hashes, projection hashes, ground
  truth, release policy hashes), computed deterministically from the config
  and the pair files.
- `results/v3/matrix-rebuild/taskB/manifests/schedule.json` — the 1680-cell
  taskB schedule with identical payloads but taskB ground truth.
- `results/v3/matrix-rebuild/{manifests,taskB/manifests}/schedule-manifest.json` —
  schedule self-hash manifests.
- `results/v3/manifests/protocol-v3-live-freeze.json` — the full live protocol
  freeze for both tasks, anchored on the one-pair validation gate run manifest.

## 2. Matrix shape

Two task matrices with identical conditions, datasets, pairs, variants,
repetitions, prompts, and model lane. They differ only in ground truth and
decision vocabulary, so every (dataset, pair, variant) has byte-identical
payloads across tasks while the label differs (task utility of the second
routing function is measured independently; Task B UIR measures whether the
synthetic internal fields shift routing decisions under B0/B1 versus the
approved-only conditions).

| Task | Dataset | Task ground truth | Decision vocabulary | Pairs | Variants | Repetitions |
|---|---|---|---|---|---|---|
| A | hmda | `hmda_review_routing_ground_truth` (DTI ≥43 or LTV ≥80 → PRIORITY) | PRIORITY_REVIEW, STANDARD_REVIEW | 20 | A, B | 3 |
| A | cfpb | `cfpb_complaint_routing_ground_truth` (debt collection or non-monetary relief → ESCALATED) | ESCALATED_REVIEW, STANDARD_REVIEW | 20 | A, B | 3 |
| B | hmda | `hmda_taskb_window_ground_truth` (action taken 4/5/6 or loan amount ≥ 500000 → PRIORITY_WINDOW) | ROUTINE_WINDOW, PRIORITY_WINDOW | 20 | A, B | 3 |
| B | cfpb | `cfpb_taskb_queue_ground_truth` (issue in {Incorrect information on your report, Opening an account} → PRIORITY_QUEUE) | STANDARD_QUEUE, PRIORITY_QUEUE | 20 | A, B | 3 |

Total per task: 7 conditions × 2 datasets × 20 pairs × 2 variants × 3 reps =
1680 executions, one OpenRouter call each; 3360 across both tasks. Task B
rules use public fields distinct from Task A rules.

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

1. 1680 cells per task; deterministic order: condition-major (B0…P3), then
   dataset (hmda, cfpb), pair, variant A/B, rep 1..3.
2. Every approved-only cell transmits exactly the dataset approved fields;
   every B0/B1 cell transmits the full record including all 6
   dataset-prohibited fields. The projection classification partitions the
   transmitted manifest (fail-closed).
3. `approvedPayloadHash` for a given (dataset, pair, variant) is identical
   across all seven conditions; P3 variants are byte-identical across
   conditions and reps; B0 variants differ only in the prohibited projection.
4. Ground truth is a pure function of approved fields (verified against the
   pair files and the pinned task functions), and taskB ground truth is
   derived from public fields distinct from taskA.
5. Every cell has a unique `contractHash` (matrixId, model, condition, variant,
   pair, rep, composed prompts, per-dataset response schema, release policy,
   seed); taskB contract hashes differ from taskA because matrixId is bound.
6. Budget: reservation €0.02/call, phase and absolute cap €40.00 per task,
   reservation total €33.60 ≤ cap; pricing semantics
   `CONSERVATIVE_USD_EUR_PARITY_CEILING`. TaskB shares the authorization
   basis, ID, and envelope but keeps its own append-only ledger.
7. The one-pair validation gate (status `PASSED_ONE_PAIR_VALIDATION`) is a
   hard anchor: the protocol freeze cannot be built or verified without it.

## 4. Cross-task consistency

`validate_matrix_config` runs taskA validation on the taskB config and then
checks that taskB matches taskA on: conditions (names, order, pinned specs),
denied fields, repetitions, seed, model lanes, validation anchor, claude lane,
prompts (system_base, purpose_clause, user), pair files, and the budget
authorization envelope (ID, basis, pricing semantics, reservation, phase cap,
absolute cap). A taskB config therefore cannot drift from taskA on anything
that would break the counterfactual.

## 5. Schedule and freeze

TaskA schedule manifest:
`results/v3/matrix-rebuild/manifests/schedule-manifest.json` (self-hash
`75c71871ffe7d20d09bae31bb9355a7c8a08fd47619d1d88f1a9d6529decb6ca`).
TaskA schedule rows hash:
`24a244720cc209aa7f31e8293b0372a93775fd730b517dcb3f66a1c058d17bd2`.

TaskB schedule manifest:
`results/v3/matrix-rebuild/taskB/manifests/schedule-manifest.json`. TaskB
schedule rows hash: `3eda22adbce86c38be20edcf437c22a6dfd8dab7ef659b06ea0767bbd3f8ac6e`.

Protocol freeze: `results/v3/manifests/protocol-v3-live-freeze.json` (hash
`65d84b6620ee4c55001bb35282233b2927a37f2570140e9225de498030e7cd1b`), status
`FROZEN_LIVE_PROTOCOL`, repository bindings research `3746cc5` / platform
`a84c24a`, anchored on the one-pair run manifest, pinning the corrected
transmission artifacts (matrix, tasks, pair gate, transmission, budget,
admission, both bridges, all build/verify scripts, both configs) and the
platform adapter sources. `verify_v3_protocol_freeze.py` recomputes both
schedules and the anchor from the current repositories and fails on any drift.

Freeze lineage (append-only, schedule hashes unchanged across all rebuilds,
TaskA `24a24472…`, TaskB `3eda22ad…`):

- `e895d2a` (commits `07f4628`/`80e9007`) — original corrected-path freeze,
  preserved at `superseded/protocol-v3-live-freeze-stale-2026-08-06-resume.json`.
- `52ef8002` (commit `7a8ddc1` added the `resume=True` continuation; `2d78ef2`
  pinned it) — resume path: validates the partial hash chain and interrupted
  ledger, archives the ledger as `<stem>.interrupted-<date>.jsonl`, settles the
  orphan reservation with `outcome="interrupted_run"`.
- `9bf0314f` (commit `b7e3f93`) — fixed the resume partial-chain validation
  (`zip(existing, cells_all, schedule_all)` no longer strict over a partial
  suffix).
- `00230b9e` (after commit `6990047`) and `09db7e0c` (commit `8b58e49`) —
  `verify_matrix_run` now accepts `RELEASE_DENIED`/`FAILED` as recorded
  outcomes (retained-failure gate: a `MATRIX_RUN_COMPLETE_WITH_RETAINED_FAILURES`
  run verifies when `released + rejected + failed_events == TOTAL_CELLS`), and
  binds the run to the **intact recorded freeze lineage** (`_recorded_freeze_with_hash`
  walks live + superseded manifests) so an append-only run manifest is never
  rewritten when the active freeze is rebuilt.
- `65d84b66` (commit `30ff338`/`3746cc5`) — `by_payload` homogeneity is now
  enforced **within a condition** (rep-to-rep) rather than across conditions:
  `payloadHash` is the hash of the full request body, and the design varies the
  body per condition (purpose clause, policy, instruction wording), so only the
  `approvedPayloadHash` cross-condition identity (verified separately) is
  invariant.

A live run manifest records the freeze hash active at run time and is bound to
it through the lineage, so verification never requires rewriting it.

## 6. Condition-count note

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

## 7. Live execution

- Live execution of the schedules is append-only and per-task (1680 calls
  each) with hash-chained events, per-cell budget reservation/settlement, and
  `verify_matrix_run` failing closed on any drift. `run_matrix` uses the
  current freeze as its live gate; its `resume=True` continuation path may only
  continue a frozen schedule after validating the partial chain and interrupted
  ledger (documented above in §5) and settles the interrupted orphan with
  `outcome="interrupted_run"`.
- Both tasks have been run and verified live against the frozen schedules:

  | Task | Run manifest | Status | Attempts | Released | Retained (denied+failed) | Committed EUR |
  |---|---|---|---|---|---|---|
  | A | `results/v3/matrix-rebuild/manifests/run-manifest.json` | `MATRIX_RUN_COMPLETE_WITH_RETAINED_FAILURES` | 1680 | 1489 | 191 | 0.066 |
  | B | `results/v3/matrix-rebuild/taskB/manifests/run-manifest.json` | `MATRIX_RUN_COMPLETE_WITH_RETAINED_FAILURES` | 1680 | 1396 | 284 | 2.061 |

  `verify_v3_matrix_run.py` fails closed on event-chain, ledger, freeze
  binding, and projection checks; the table is presented here for record, and
  the analysis artifacts (per-condition outcomes, UIR / IRQ metrics, D0-D3,
  attack suite) are downstream phases.

## 8. Not in scope of this phase

- Attack suite families (separate phase, per REDUCED_SCOPE_SUMMARY.md next steps).
- D0-D3 differential-privacy aggregation conditions (require a DP ledger).
- No AWS Nitro, no confirmatory claims, no paper submission.
