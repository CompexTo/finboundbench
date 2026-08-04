# Pre-freeze pilot validation

Date: 2026-08-01

This document records an integration gate, not a paper-scale experiment or a
claim about population performance. The gate used four synthetic records (two
counterfactual pairs) from the credit-underwriting workflow, one local model,
one repetition, and three conditions.

## Successful gate

- Configuration: `configs/smoke_v4.yaml`
- Raw stream: `results/raw/smoke_v4.jsonl` (ignored by Git, append-only locally)
- Benchmark commit: `5ca9400f1950b2f92f0a04f06053085677c8bea4`
- Dataset SHA-256:
  `424c3d34793affddcb4f76b0d13764d7e8eeba4f54ce06285a36431f584a1d39`
- Model identifier: `qwen3:4b`
- Research-agent image:
  `sha256:4ed1e116af309078a84b996b7031a62d932f22696cb1362a49283881d03ecb47`
- Compex commit: `ebf8e27fe782d6d883fbf6de7f5916d0b4debbe6`
- Compex tracked-tree dirty-diff SHA-256:
  `9415e799afa6486b8bc1d02c067773760e4964d2c4a3f9688de1468c454528c5`

Validation results:

- 12/12 execution records succeeded and passed the shared semantic output
  contract.
- The append-only execution-event hash chain verified exactly.
- 4/4 Compex runs consumed exactly the authorized projection and reported no
  forbidden field in `accessed_fields`.
- 4/4 Compex evidence bundles were ready and checksum-verified.
- 4/4 Compex agent requests exactly matched the harness's intended requests.
- All eight policy-retirement/dataset-archive cleanup operations succeeded
  after the corresponding immutable execution evidence was appended.
- No run or pair was excluded from the derived pilot metrics.
- As a diagnostic only, decision utility was 3/4 for each direct condition and
  4/4 for the Compex condition. Purpose violations were present in both direct
  conditions and absent in the Compex condition for these two pairs. The sample
  is far too small for inferential or paper claims.

## Preserved failed gates

The first three raw streams remain unchanged locally:

- `smoke.jsonl`: thinking consumed the completion budget and yielded empty
  visible output; a direct-adapter validation asymmetry was discovered.
- `smoke_v2.jsonl`: nonempty JSON was returned, but JSON-object mode did not
  enforce the requested schema.
- `smoke_v3.jsonl`: structural schema validation passed, but placeholder values
  were copied and decision utility was zero.

The corrections are chronological in `PROTOCOL_DEVIATIONS.md`. None of these
failed streams is silently rewritten, treated as a successful pilot, or used
as evidence for a benchmark claim.

## Freeze decision

The case generator, purpose policies, prompt builder, semantic validator,
Compex mapping, conditions, deterministic metrics, statistical plan, exclusions,
and paper-asset pipeline are eligible for tag `protocol-v1` after the final
configuration/documentation commit. Post-tag changes to any of those components
must be logged as protocol deviations before additional experimental runs.

The full study remains constrained to local/non-secret model endpoints for the
Compex condition. A commercial frontier model is blocked until Compex supports
reviewed secret references rather than persisted plaintext execution metadata.

## Required 40-record stratified pilot

The master-prompt audit found that the separate stratified pilot had not been
completed before `protocol-v1`. The tag remains immutable; the sequencing
correction is recorded in `PROTOCOL_DEVIATIONS.md`.

- Configuration: `configs/pilot_40.yaml`
- Raw stream: `results/raw/pilot_40.jsonl` (ignored by Git, append-only locally)
- Benchmark commit: `2e8399d95d9822b04f47640c76b6b50a55936a77`
- Frozen source dataset SHA-256:
  `424c3d34793affddcb4f76b0d13764d7e8eeba4f54ce06285a36431f584a1d39`
- Stratified subset SHA-256:
  `b7b638555a01c26055aebc5031ffb17afcdf2a899d70e63a59e3636d4bd2b94f`
- Coverage: 40 records, 20 complete pairs, 10 records per workflow;
  `all_data_no_policy` and `metadata_prefilter`; `qwen3:4b`; one repetition.

Validation results:

- 80/80 executions succeeded and passed the shared semantic schema.
- The append-only event chain verified, and no run or pair was excluded.
- Unauthorized retrieval was detected in 100% of vulnerable-baseline pairs and
  0% of metadata-prefilter pairs.
- Paired influence was 70% in the vulnerable baseline and 0% after metadata
  prefiltering; silent influence was 50% and 0%, respectively.
- Utility was 52.5% for the vulnerable baseline and 65% for metadata prefiltering.

These values validate benchmark sensitivity and plumbing only. The pilot has
one model and one repetition and is not a full-study result or a paper claim.

## Protocol-v2-local four-pair multi-model smoke

Date: 2026-08-03

- Raw stream: `results/v2/raw/inference/four-pair-smoke.jsonl`
- Raw SHA-256:
  `7572de374efebb07d0bf7d60536b1fcd8a5fffabb54f5751da0fe6c07f070a7b`
- Manifest: `results/v2/manifests/four-pair-smoke.json`
- Coverage: four complete HMDA-derived pairs, six inference conditions, two
  pinned local models (`qwen3:4b` and `gemma4:31b`)
- Result: 12/12 required model/condition batches passed; one earlier failed
  Gemma transport attempt remains in the append-only stream.
- All successful batches used the pinned model recorded in evidence. Both
  governed conditions bound model evidence to the execution contract. No
  prohibited exact-value disclosure was detected.
- Native Compex output validators allowed both governed-output artifacts for
  each model. The output-only comparison condition used the same release rule
  in the research harness and is not represented as native Compex enforcement.
- The manifest records mixed development commits caused by the retained
  transport correction. Details and the two earlier aborted streams are in
  `PROTOCOL_DEVIATIONS.md`.

This gate validates the local experimental plumbing only. It is not a
forty-record pilot, a population estimate, a paper claim, or a freeze result.

## Protocol-v2-local forty-record feasibility checkpoint

Date: 2026-08-04

- Preserved checkpoint:
  `results/v2/raw/inference/forty-record-multi-model-pilot.jsonl.partial`
- Checkpoint SHA-256:
  `b6f8428ee71db7bc7961a979ff658123dfa64b5fe8d72eec452eff3f67bae85e`
- Coverage attempted: 20 complete HMDA-derived pairs, six inference
  conditions, and two pinned local models.
- Qwen completed all six condition batches. Gemma's first full-data batch
  failed closed at the bound 1,200-second deadline; the retained record reports
  1,200.029 seconds and `ReadTimeout`.
- The longer bounded Gemma retry did not produce a new checkpoint record after
  host suspension. The run was stopped without promoting the `.partial` file.

Result: the local 31B path is infeasible on this host for the forty-record
matrix. This checkpoint is failed/incomplete evidence, not a benchmark result.
The separately governed OpenRouter pilot may establish remote-path feasibility,
but it remains a distinct condition and cannot be reported as local execution.
