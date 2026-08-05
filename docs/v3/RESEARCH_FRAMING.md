# Research framing

Status: preregistration draft; results language is prohibited until freeze  
Anonymous implementation label: **PSBE-Runtime**

## Central question

Can a financial AI system gain legitimate utility from a confidential attribute
for an approved purpose while demonstrably preventing that same attribute from
influencing a different, prohibited purpose—and can the boundary survive
substitution, lifecycle, capability, release, privacy, and evidence attacks?

The question is about selective use, not mere secrecy. Encryption or enclave
execution can hide data from infrastructure operators while still permitting a
workload to use the wrong field for the wrong purpose. Conversely, deleting all
confidential fields can prevent misuse while destroying the utility that
motivated confidential computation.

## Research objects

- **PSBE** is the abstract control model: an approved purpose is bound to an
  exact dataset projection, workload/model identity, tools and network routes,
  release validators, privacy budget, lifecycle state, and evidence contract.
- **FinBoundBench** is the benchmark: two purpose tasks, paired confidential
  counterfactuals, honest and adversarial executions, component ablations, and
  preregistered metrics.
- **PSBE-Runtime** is the anonymous reference implementation. It is one system
  under test, not the definition of PSBE and not evidence of generality.

## Intended contributions

1. A formal, falsifiable definition of purpose-selective bounded execution and
   its host, model, provider, and application threat boundaries.
2. A semi-synthetic financial benchmark in which the approved task benefits
   from a clearly synthetic confidential attribute and the prohibited task has
   paired, invariant ground truth.
3. A fair comparison among full-data, prompt-only, deterministic hardened
   filtering, and layered PSBE conditions.
4. A cross-layer attack matrix that distinguishes prevention, fail-closed
   denial, silent compromise, detection after the fact, and evidence failure.
5. Reconstructable evidence and paired security–utility–availability–overhead
   statistics, including DP training/release experiments.

## Explicit non-contributions

The study does not introduce confidential computing, TEEs, differential
privacy, DP-SGD, remote attestation, provenance, policy engines, purpose-based
access control, output guardrails, agent capability systems, or joint
security–utility evaluation in general. It does not show regulatory compliance,
production fitness, fairness, or absence of all leakage. It does not claim that
synthetic internal signals describe real customers.

## Core design tension

FinBoundBench must prevent a trivial win by field deletion. Every confidential
attribute has two roles:

- **Task A — approved use.** The purpose contract authorizes the attribute, and
  the benchmark construction makes it incrementally predictive. A system that
  removes it should lose authorized utility.
- **Task B — prohibited use.** The purpose contract denies the same attribute,
  public fields and ground truth remain identical within each counterfactual
  pair, and any output change is prohibited influence.

The primary result is therefore a frontier, not a single success percentage:
authorized utility retained versus unauthorized influence, with availability,
privacy, evidence coverage, and overhead alongside it.

## Unit of analysis and generalization

The independent sampling unit is the public-source base record, represented by
a paired synthetic-confidential counterfactual. Model repetitions and both
variants are repeated measurements, not extra independent samples. Inference
generalizes only to the sampled public records, declared semi-synthetic task,
exact model versions, routes, and runtime build. Dataset, task, and model
heterogeneity are reported rather than hidden by an undifferentiated average.

## Claims permitted before and after freeze

Before the confirmatory freeze, documents may say “designed to,” “tests,” or
“candidate contribution.” They may not say “prevents,” “preserves,” “reduces,”
or “outperforms” without identifying a frozen result and uncertainty interval.

After freeze, each result statement must link to:

1. the preregistered hypothesis and estimand;
2. raw immutable events and their manifest hashes;
3. deterministic analysis code;
4. the produced table/figure cell; and
5. limitations and deviations affecting interpretation.

## Decision rule for paper viability

The paper is viable only if all of the following hold:

- Task A shows a measurable approved-attribute benefit in at least one dataset
  without relying on label leakage or a synthetic tautology.
- Task B is sensitive enough that at least one weak baseline exhibits
  prohibited influence.
- The hardened prefilter comparison is retained and honestly interpreted.
- At least one layered PSBE component has measurable value beyond honest-case
  filtering, or the null result itself is analyzed rigorously.
- evidence verification, availability, and overhead are reported for failures
  as well as successes.
- no pilot or failed record is silently removed.

If these conditions fail, the correct output is a negative-results report or a
redesigned future protocol, not a positive paper claim.
