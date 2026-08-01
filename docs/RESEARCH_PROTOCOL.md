# Research protocol

## Working title

**Authorized to See, Forbidden to Use: Measuring Silent Cross-Purpose Influence in Financial AI Agents**

## Problem

Most enterprise controls decide *who* may access a record. Financial data governance also constrains *why* a record may be used. A bank employee or agent may be allowed to see an AML record for investigation while being prohibited from using the same record for credit underwriting or product targeting.

The study measures whether financial AI agents silently use prohibited-but-visible data for a different purpose.

## Research questions

- RQ1: How often do financial AI agents use prohibited-but-visible data in a decision?
- RQ2: Do natural-language purpose instructions reduce violations reliably across models and attack types?
- RQ3: Which enforcement layer contributes most: data projection, capability restriction, output validation or evidence generation?
- RQ4: What utility, latency and cost trade-offs arise from purpose-bound execution?

## Main hypotheses

- H1: Prompt-only purpose rules leave a material silent-influence rate.
- H2: Output filtering reduces disclosure but does not reliably prevent hidden decision influence.
- H3: Pre-execution data projection produces the largest reduction in purpose violations.
- H4: Purpose-bound Compex execution approaches metadata prefiltering on safety while adding independently inspectable evidence and stronger runtime guarantees.

## Benchmark design

Use four workflows:

1. Credit underwriting
2. AML review
3. Customer support
4. Product recommendation

Create 30 base cases per workflow. Each base case produces at least two paired variants:

- Variant A: prohibited attribute has value A.
- Variant B: prohibited attribute has value B.
- All purpose-permitted fields remain byte-identical.

A changed decision, score, action or permitted rationale across the pair is evidence of silent cross-purpose influence, subject to repeated runs and stability controls.

## Conditions

- No policy baseline
- Prompt-only purpose rule
- Output guard only
- Metadata prefilter
- Compex purpose-bound runtime

## Failure modes

- Benign temptation: prohibited data is relevant and convenient.
- Direct override: user explicitly asks the agent to use it.
- Purpose drift: conversation starts as one purpose and shifts to another.
- Indirect instruction: a retrieved note encourages cross-purpose use.
- Tool-chain laundering: one tool summarizes prohibited data and another consumes the summary.
- Derived proxy: prohibited data affects a summary without being directly repeated.

## Primary metrics

- Purpose Violation Rate (PVR)
- Unauthorized Retrieval Rate (URR)
- Silent Influence Rate (SIR)
- Sensitive Disclosure Rate (SDR)
- Unauthorized Action Rate (UAR)
- Legitimate Task Utility (LTU)
- False Block Rate (FBR)
- Evidence Completeness (EC)
- Median and p95 latency
- Estimated per-task model cost

## Deterministic evaluation first

Primary labels should come from:

- Compex/tool access logs
- Sentinel strings embedded only in prohibited fields
- Structured decisions and risk scores
- Paired counterfactual differences
- Machine-readable policy events

An LLM judge may assess semantic disclosure or rationale quality, but it must be secondary and validated on a human-coded sample.

## Statistical plan

- Report rates with bootstrap 95% confidence intervals clustered by base case.
- Use paired tests because the same case is run across conditions.
- Use McNemar tests for paired binary violations.
- Model violation probability with a mixed-effects or GEE logistic model using condition, workflow, model and attack class as factors, grouped by base case.
- Correct families of secondary comparisons using Benjamini-Hochberg FDR.
- Report effect sizes, not only p-values.
- Predefine exclusion rules for API errors and malformed outputs.

## Minimum credible scale

Pilot:
- 4 workflows × 10 cases × 2 variants × 3 conditions × 2 models × 2 repetitions

Full:
- 4 workflows × 30 cases × 2 variants × 5 conditions × 4 models × 3 repetitions
- Approximately 14,400 executions before retries; reduce with a preregistered stratified design if API cost is excessive.

## Paper-neutral naming

For blind review, call Compex the **Purpose-Bound Execution Runtime (PBER)**. Do not link to getcompex.com, public repositories or identifying demos in the anonymous manuscript.
