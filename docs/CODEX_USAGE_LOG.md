# Codex contribution log

Human authors must inspect and validate every material component listed here.
Codex is a tool used in the research process and is not an author.

## 2026-08-09

- Completed the v4 confirmatory phase: execution windows (primary-2,
  replication-8), deterministic P2 runs, statistical reports (primary,
  replication, combined), and six freeze manifests. Both studies pass the
  fixed-sequence chain H1-H2-H3-H5-H6 (interpretation rule 1).
- Corrected the replication results freeze so every bound file carries a
  per-file SHA-256 (previously only a plain path list); self-hash verified
  (`c56f4dcf...`).
- Implemented `scripts/run_v4_verification_bundle.py` — an independent
  verification bundle (Phase 12 style, marked internal) that re-derives the
  headline metrics from the frozen raw events with a fresh implementation and
  cross-checks all six manifests, bound-file hashes, event-stream accounting,
  and report self-hashes.
- Produced `results/v4/evidence/confirmatory-verification-bundle.json`
  (15 checks, VERDICT: PASS).
- Reviewed `ROADMAP_FULL.md`: phases 9 (baseline/unfairness), 10 (attacks),
  11 (separate protocol), 13 (AWS) have no registered v4 specs and are marked
  "later"/"separate family"; Phase 12 external verification is gated on
  authorization. No methodology was fabricated for unregistered phases.

Required human review areas include the purpose policies, equivalence of the
Compex two-stage execution to comparison conditions, metric definitions,
statistical plan, model selection, cost assumptions, exclusions, and all paper
interpretation.

## 2026-08-01

- Initialized this benchmark as a separate nested Git repository on branch
  `research/purposebound-finance`; did not edit tracked Compex platform files.
- Inspected the local Compex source, Compose topology, API DTOs, policy checks,
  worker/runner flow, audit chain, and evidence bundle implementation.
- Wrote `COMPEX_LOCAL_MAPPING.md` from that read-only inspection.
- Implemented the Compex adapter orchestration and the research-owned local
  model-agent container.
- Added fake-local-server adapter contract tests and fail-closed evidence tests.
- Hardened paired synthetic generation, manifests, run provenance, immutable
  event chaining, retry evidence, deterministic evaluation, statistical tests,
  exclusions, and raw-to-paper asset generation.
- Generated no numerical research claim and used no customer, employer, or
  private production dataset.
- Ran a pre-freeze real smoke test, diagnosed a thinking-model structured-output
  failure, and implemented the documented fail-closed correction without
  modifying the original raw event stream.
- Preserved three unsuccessful pilot streams, completed the fourth integration
  gate, generated deterministic pilot diagnostics, and prepared the validated
  protocol for versioning. Pilot values are not presented as paper claims.
- Added a deterministic stratified selector after an instruction audit,
  completed the required 40-record/two-condition pilot, and regenerated its
  metrics from the immutable raw event stream.

Required human review areas include the purpose policies, equivalence of the
Compex two-stage execution to comparison conditions, metric definitions,
statistical plan, model selection, cost assumptions, exclusions, and all paper
interpretation.
