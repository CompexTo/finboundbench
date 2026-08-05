# Gate 5: no-cost non-TEE dry run

Status: `PASSED_INSTRUMENTATION_ONLY`  
Execution date: 2026-08-05  
Freeze self-hash:
`eb669c715514da952b751dcc2a7c63df91e3ee78b6c6b6fa0ffa55c34fabb29f`  
Run-manifest self-hash:
`749da835f862e1c78546569b042d9c6353079b725d5d98c8da6221be41aa6f99`

## Exact scope

The retained run exercised protocol scheduling, data-pair construction,
condition visibility, three immutable deterministic model lanes, three
repetitions, structured assessments, metric aggregation, every registered
attack ID and outcome state, four privacy lanes, append-only event hashing,
manifests, independent verification, and raw-to-derived regeneration.

It did not call a model provider, read a provider secret, train a DP model,
measure real security/privacy/latency, use AWS, or use a TEE. Every event says
`INSTRUMENTATION_ONLY_NOT_A_RESEARCH_RESULT`. Paper result placeholders and
claim traceability remained unchanged.

## Scheduled and retained events

| Event class | Count |
| --- | ---: |
| inference batches | 504 |
| attack attempts | 705 |
| privacy test-double runs | 12 |
| **total hash-chained events** | **1,221** |

The inference schedule covered two datasets, Tasks A/B, B0–P3, three models,
three repetitions, and separately batched A/B variants. The attack schedule
covered all 57 stable IDs over their registered applicable conditions. The
privacy schedule covered D0–D3 over three dry-run seeds.

## Development-data gates

The 40 public-source base-record pairs (80 variants) produced:

- public-only Task A reference accuracy: 0.80;
- authorized-oracle Task A accuracy: 0.90;
- planning oracle gain: 0.10 (floating representation retained as
  `0.09999999999999998` in JSON);
- Task A and Task B prevalence: 0.50 each;
- confidential-only Task A accuracy: 0.40; and
- byte-identical public fields and invariant Task B ground truth within every
  pair.

These values validate semi-synthetic task sensitivity. They are constructed
development-fixture properties, not model results.

## Attack and privacy sensitivity

The deterministic attack oracle produced 504 `PREVENTED`, 171
`SILENT_COMPROMISE`, and 30 `SUCCEEDED_DETECTED` classifications. Those counts
prove that the analysis handles multiple outcomes and differentiates layers;
they say nothing about an actual model or adversary.

All 12 privacy values are labeled `TEST_DOUBLE_NOT_DP_TRAINING`; secure RNG is
false. They validate configuration/analysis routing only. No epsilon or leakage
value from this run may appear as an empirical claim.

## Integrity and reproduction

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| generated development pairs | 144,714 | `79139d3bd6f117142c3edea6571e49a387435feacaf5f718d09135a15ab3c72d` |
| raw events | 7,712,976 | `3fd4697fddba379b3531401d18b95194fe9067279edfb40ca579e8712467e113` |
| derived instrumentation report | 29,132 | `f3ed6cd9084cf437233f52246938a2b23db3cd3785e354cb9d525bc50ecac94f` |

The verifier ran in a fresh process against retained files. A second complete
run in a fresh temporary directory regenerated all three hashes exactly and
reproduced the run-manifest self-hash. A targeted scan found no OpenRouter key
prefix, secret environment name, bearer token, or API-key field in the dry-run
namespace.

## Costs and external actions

- provider calls: 0;
- paid cost: EUR 0;
- paid secret reads: 0;
- AWS actions: 0;
- hardware-attestation claims: false.

## Pre-execution failed freeze retained

Freeze attempt 1 rejected its own 40-character Git bindings because the new
validator initially accepted only 64-character IDs. No official run had
started. The failed manifest is retained by commit and explicit invalid-attempt
record; `docs/v3/PROTOCOL_DEVIATIONS.md` documents the correction. The official
run binds only the corrected freeze.

## Remaining gates before paid readiness

1. Resolve the confirmatory protocol placeholders: exact current model lanes,
   batch/position admission, and DP epsilon calibration with secure RNG.
2. Decide whether to implement durable multi-worker privacy accounting or
   narrow the DP claim to a research-local ledger.
3. Add/verify the research-to-platform adapter that directly invokes all P0–P3
   layers, rather than relying on component tests plus a Python test double.
4. Run real local open-weight model gates where three immutable lanes are
   available and retain failures.
5. Build the ACM PDF in an installed LaTeX environment and complete human
   anonymity review.
6. Freeze the confirmatory sample, order, prompt/schema, models, analysis code,
   and numeric cost cap.

Only after these gates pass is it appropriate to request `OPENROUTER_API_KEY`.
AWS/TEE work remains prohibited until the non-TEE empirical results freeze.
