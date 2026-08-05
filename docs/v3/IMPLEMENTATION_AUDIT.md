# PSBE-Runtime implementation audit

Audited: 2026-08-05  
Platform branch: `research/psbe-runtime-v3`  
Audit implementation commit: `f5494b2`  
Historical v2 platform commit remains: `29e4b2e`

## Outcome

The platform contains substantial generic confidential-execution primitives,
but they are not yet one universally mediated production execution path. The v3
study may directly exercise the reviewed components and call that a reference
implementation; it may not claim that every existing product run is governed by
PSBE. The main missing verifier capability was implemented. Durability and
end-to-end orchestration gaps remain explicit blockers for stronger claims.

## Component audit

| Surface | Evidence inspected | Finding | v3 disposition |
| --- | --- | --- | --- |
| purpose contract | shared confidential-execution types, validation, Prisma contract service/migration | exact data, policy, workload/model, capability, release, privacy, approval, expiry, revision, supersession, and revocation fields exist | directly test lifecycle and substitution paths |
| persistence integrity | append-only contract/event schema and database triggers in the purpose-bound migration | material/evidence mutation protections exist for those tables; no global proof over every operational store | include DB tests where available; do not say “immutable platform” |
| projection | `platform-data-preparation.ts` | deterministic allowlisted projection and source/artifact/manifest binding exist; complex SQL/alias/join surfaces are rejected | use for P0–P3; require byte equality with B2 honest input |
| local boundary | runner hardened Docker backend and managed boundary | non-root/read-only/capability-free/no-network/resource-bounded execution and exact artifact checks exist | supported non-TEE backend; host remains trusted |
| release | `native-output-release.ts` | stable fail-closed schema, vocabulary, numeric, size, exact-value, field-name, PII, cohort, artifact, model, human-approval, and privacy validators exist | use for P1–P3 and retain every validator event |
| capabilities | `purpose-capability-enforcer.ts` | default-deny tool/network controls, exact model endpoint/provider, encoded-value scanning, call/byte limits, and hash-chain events exist | use for P2–P3; component is not imported by a single API orchestration service today |
| privacy | `privacy-budget-ledger.ts` and DP analysis | reservation consumes budget before release; commit/rollback/denial form a hash chain; DP helpers exist | ledger is process-memory only, not durable across workers/restarts; confirmatory persistence/concurrency claim blocked |
| DP training | v2 Opacus validation and privacy modules | real DP-SGD/accountant plumbing exists; v2 validation explicitly disabled secure RNG | v3 confirmatory DP requires secure RNG and ten-seed calibration; v2 numbers remain diagnostic only |
| evidence integrity | evidence v2 builder/verifier | deterministic components and externally pinned root detect post-commit mutations | retained without changing frozen v2 semantics |
| evidence semantics | evidence v2 independent verifier | did not independently re-appraise cross-component semantic bindings after a new commitment | implemented generic v3 semantic verifier at platform commit `f5494b2` |
| remote providers | runner commercial adapters and OpenRouter v2 controls | exact route/model/schema, no-fallback, bounded retries, secret references, diagnostics exist | paid v3 remains blocked; re-admit current models/routes only after dry-run freeze |
| TEE | backend interface and Nitro stub | Nitro returns `NOT_CONFIGURED`, `hardwareAttestation=false`, and never fabricates attestation | correct behavior; no AWS action before non-TEE freeze |

## Implemented generic capability

`services/api/src/confidential-execution/evidence-v3/evidence-semantic-verifier.ts`
adds an independent 16-claim appraisal over an externally anchored v2 evidence
root. It checks:

- canonical contract validity and execution readiness at evidence generation;
- identity, dataset, projection, policy, approval, workload, and exact-model
  bindings;
- privacy settings and a matching budget-ledger record;
- exact secret-reference metadata without secret values;
- allowed network/tool evidence against declared destinations, permissions,
  calls, bytes, and protected-value policy;
- release artifact types and all mandatory native validator ALLOW events;
- audit hash chain, tenant context, and contract-hash presence; and
- cleanup, retention, and mandatory component commitments.

The verifier deliberately requires an externally supplied root; it does not
default to trusting the bundle's own root. Tests construct dataset, release, and
cross-tenant audit substitutions, recompute every affected component commitment
and the evidence root, demonstrate that integrity alone accepts the new
commitment, and then demonstrate semantic rejection.

## Verification results

Under local Node `v22.23.1`:

- API TypeScript typecheck: passed;
- API confidential-execution suites: 12 suites, 142 tests passed, including 4
  new semantic-verifier tests;
- runner: 32 tests passed;
- v2 research freeze tests and derived-analysis reproduction remained unchanged.

The default system `node` is `v16.20.2`; the existing privacy tests fail there
because the existing ledger uses `structuredClone`. This is an environment
compatibility fact, not a v3 regression. The v3 runtime manifest must pin Node
22 and must not report a Node-16 suite pass.

## Remaining gaps and claim limits

### G1 — universal mediation is not established

A production-source search finds the capability enforcer, release evaluator,
privacy ledger, evidence builder, and semantic verifier only in their component
modules, not imported together by one API orchestration service. Component
tests therefore establish the behavior of directly invoked boundaries, not that
all current execution routes traverse them.

**Disposition:** the no-cost study directly invokes each layer through a
research adapter and records that scope. A later production claim requires a
single orchestrator/integration test showing that every governed effect and
release is mediated.

### G2 — privacy accounting is not durable

The ledger is transactional only within one in-memory instance. A restart or
multi-worker deployment can lose/resplit state unless an external durable store
serializes reservations and scope updates atomically.

**Disposition:** no production privacy-budget claim. The no-cost dry run tests
the library and restart/concurrency attacks as expected failures or blocked
capabilities. A future generic Prisma/transactional ledger is separate platform
work and must be migration-reviewed.

### G3 — external root anchoring is supplied, not implemented

The v3 verifier requires a separately trusted root, but the current change does
not sign it or publish it to a transparency log.

**Disposition:** the research freeze manifest is the independent local anchor.
The paper says “externally manifest-anchored,” not “publicly notarized.”

### G4 — three confirmatory model lanes are not admitted

Existing v2 model manifests are historical. Current model availability, route,
price, seed behavior, and schema compatibility must be checked later.

**Disposition:** use three deterministic test-double lanes for instrumentation
only; request a provider key and numeric cost cap only after paid readiness.

### G5 — TEE is intentionally absent

No attestation evidence, key release, or AWS environment exists. Docker is not a
TEE.

**Disposition:** preserve the non-TEE trust statement and stop before AWS.

## Frozen-v2 preservation

No v2 research file was edited. The platform change adds a separate `evidence-v3`
module and `test/unit/v3` suite; it does not change evidence-v2 construction or
verification behavior. The v2 manifest continues to bind its historical
platform/research commits and artifact hashes.
