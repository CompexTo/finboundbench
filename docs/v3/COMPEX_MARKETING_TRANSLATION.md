# Internal marketing translation guardrail

This file is not a press release. It maps possible frozen research outcomes to
language that may be considered after peer review. Until results freeze, all
items remain hypothetical.

## Names

- Academic method: Purpose-Selective Bounded Execution (PSBE)
- Benchmark: FinBoundBench
- Anonymous implementation: PSBE-Runtime
- Product mapping after anonymity is no longer required: Compex confidential
  execution / purpose-bound contracts, with exact product naming chosen by the
  product owner

## Language table

| Evidence state | Language allowed | Language prohibited |
| --- | --- | --- |
| protocol and tests only | “designed to bind purpose, data, workload, capabilities, release, and evidence” | “prevents misuse,” “proven secure,” “compliant” |
| no-cost test-double dry run | “benchmark instrumentation passed its synthetic dry run” | any claim about real models, customers, providers, or security effectiveness |
| frozen non-TEE empirical reduction | “in the registered benchmark, exact build X reduced observed prohibited influence from A to B” | “eliminates unauthorized use,” “works for all financial AI” |
| evidence verification result | “Y% of registered bundles independently verified under the benchmark rules” | “immutable audit trail” without stating trusted storage/host assumptions |
| DP result | report exact epsilon/delta, utility, attack metric, seeds, and secure-RNG state | “anonymous,” “zero leakage,” or “GDPR compliant” |
| future attested result | name exact hardware/backend/measurement and compare separately | applying TEE trust claims to earlier non-TEE executions |

## Product-relevant questions the research can answer

- Does approved confidential data add measurable task value instead of being
  deleted indiscriminately?
- Does the same field cease to affect a prohibited purpose under paired tests?
- Which runtime layer changes prevention, detection, evidence, availability,
  and overhead relative to a strong prefilter?
- Can an independent verifier reconstruct the claimed contract and release
  path from retained artifacts?

It cannot answer legal compliance, customer-specific risk, production scale,
fairness, or resistance to an untrusted host without additional evaluation.

## Publication discipline

Marketing review begins only after:

1. raw and derived results freeze;
2. claim traceability links every number;
3. limitations and null results are approved with the positive results;
4. venue anonymity/publicity rules permit identification; and
5. security and legal reviewers approve exact wording.

If a headline cannot include the benchmark scope and trust boundary without
becoming misleading, do not use it.
