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
