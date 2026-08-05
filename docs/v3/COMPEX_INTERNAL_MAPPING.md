# Internal mapping: PSBE-Runtime to the Compex platform

This document is internal and must not enter an anonymous review artifact.
Public research artifacts use **PSBE-Runtime** only.

## Current generic primitives

| PSBE concept | Current Compex location | Audit status for v3 |
| --- | --- | --- |
| immutable purpose/data/workload/model/capability/release contract | `packages/types/src/confidential-execution.ts` | broad schema exists; v3 protocol naming and end-to-end orchestration must be verified |
| approval, revision, expiry, revocation, current-version checks | `services/api/src/confidential-execution/contracts/purpose-bound-contracts.service.ts` and purpose-bound migration | implemented service paths; persistence/concurrency tests required |
| exact dataset projection and source hash | `services/api/src/confidential-execution/preparation/platform-data-preparation.ts` | implemented allowlist projection; use as P0 path |
| native fail-closed release | `services/api/src/confidential-execution/release/native-output-release.ts` | broad validator chain exists; attack coverage must map to stable IDs |
| tool/network/data-flow limits | `services/api/src/confidential-execution/capability-enforcement/purpose-capability-enforcer.ts` | generic enforcer exists; universal mediation in real execution path not yet established |
| privacy budget and DP analysis | privacy ledger and DP analysis modules under confidential execution | useful primitives; durable transactional ledger and production secure-RNG DP path not established |
| evidence component/root verification | `services/api/src/confidential-execution/evidence-v2/evidence-v2.ts` plus `evidence-v3/evidence-semantic-verifier.ts` | v2 integrity plus 16-claim semantic verifier implemented at platform commit `f5494b2`; external root anchoring and orchestration integration remain |
| hardened non-TEE execution | runner local hardened Docker backend | implemented and tested; host remains trusted |
| remote commercial model | commercial/OpenRouter adapter | v2 route controls exist; v3 paid execution remains blocked |
| TEE/Nitro | confidential backend interface and Nitro stub | correctly `NOT_CONFIGURED`; excluded until non-TEE freeze |

## Condition routing

- B0/B1 are research-owned controlled-exposure adapters and must never be
  described as production Compex defaults.
- B2 is a research-owned strong comparator using the same exact projection and
  hardened Docker constraints, but without Compex purpose lifecycle and full
  evidence semantics.
- P0–P3 exercise successively broader Compex generic primitives under the
  anonymous PSBE-Runtime label.
- D0–D3 use the generic privacy ledger/training path after durability and secure
  configuration checks.

## Required implementation boundary

Research code may add adapters, fixtures, manifests, independent verification,
and deterministic analysis. Platform changes must remain generic: no HMDA/CFPB
field names, paper-specific conditions, benchmark labels, or hard-coded study
results in production services.

The research repository owns protocol semantics and maps them onto platform
capabilities. The platform must not import research code.

## Evidence identity

Every v3 evidence bundle records both repositories' exact commits and dirty
state, but anonymous paper assets replace those identities with stable artifact
labels. The private mapping remains in the retained internal manifest and is
not uploaded during double-blind review.

## Current audit conclusion

Compex already contains most component primitives, so a claim that v3
“implemented purpose-bound execution from scratch” would be false. The key
engineering question is complete mediation and durable binding across the
production execution path. Library-level unit tests alone do not establish that
property. Gate 4 must either wire and verify the generic gaps or narrow the
experimental claim to the directly exercised paths.
