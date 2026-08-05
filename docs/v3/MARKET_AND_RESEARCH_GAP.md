# Market and research gap: purpose-selective bounded execution

Status: protocol design, not a claim of completed empirical results  
Review cutoff: 2026-08-05  
Public names: **Purpose-Selective Bounded Execution (PSBE)**,
**FinBoundBench**, and **PSBE-Runtime**

## Scope and review method

This review asks a narrow question: what is already available for protecting
financial data during AI computation, and what has not yet been measured by a
public benchmark? It separates product capabilities, research prototypes,
standards, and evaluation datasets. Vendor statements are treated as claims by
their vendors, not as independent evidence. Absence claims are deliberately
bounded to the primary sources and public documentation reviewed by the cutoff
date.

## Existing market capabilities

| Category | Representative systems | Capability already available | Boundary relevant to this study |
| --- | --- | --- | --- |
| Confidential collaboration and clean rooms | [AWS Clean Rooms](https://docs.aws.amazon.com/clean-rooms/latest/userguide/what-is.html), [Decentriq on Azure](https://learn.microsoft.com/en-us/azure/confidential-computing/partner-pages/decentriq) | Controlled multi-party analytics, query rules, cryptographic computing, differential privacy, and confidential-computing deployments | Primarily collaboration/query or protected-computation products; public material does not report the paired purpose-selective AI benchmark proposed here |
| Attested confidential analytics | [Opaque](https://www.opaque.co/product), [Opaque NSDI paper](https://www.usenix.org/conference/nsdi17/technical-sessions/presentation/zheng) | Attested confidential VMs/enclaves, runtime policies, encrypted analytics, and audit evidence | Strong host/data confidentiality; not evidence that an approved attribute improves one financial purpose while being causally irrelevant to another |
| Confidential AI platforms | [Fortanix Confidential AI](https://resources.fortanix.com/hubfs/Solution_briefs/Confidential-AI-Solution_Brief.pdf), [Azure confidential AI](https://learn.microsoft.com/en-au/azure/confidential-computing/confidential-ai) | Enclave execution, attestation-conditioned key release, model/data protection, governance controls | Host and asset protection are not themselves purpose-selective use control or a comparative benchmark |
| Verifiable confidential inference | [Tinfoil inference](https://tinfoil.sh/inference), [Tinfoil verification architecture](https://docs.tinfoil.sh/verification/attestation-architecture) | OpenAI-compatible inference in attested enclaves, encrypted channels, public verification material | Useful future backend; does not replace application-level projection, capability, release, privacy-budget, and evidence semantics |
| General policy engines | [OPA decision logs](https://www.openpolicyagent.org/docs/management-decision-logs), [OPA bundles](https://www.openpolicyagent.org/docs/management-bundles), [Cedar](https://docs.cedarpolicy.com/) | Externalized authorization, policy validation, decision logging, bundle distribution | They decide requests expressed by an application. They do not define the financial purpose contract, construct a minimal projection, or prove end-to-end adherence on their own |
| Model guardrails | [NeMo Guardrails](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/how-it-works), [Amazon Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-how.html) | Input, retrieval, dialog, tool/execution, and output controls | Guardrails are relevant baselines, but prompt/output rails alone do not establish non-influence of a prohibited field |
| Attestation and provenance standards | [IETF RATS architecture](https://www.rfc-editor.org/rfc/rfc9334.html), [in-toto](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias), [SLSA provenance](https://slsa.dev/spec/v1.2/provenance), [Sigstore bundles](https://docs.sigstore.dev/about/bundle/) | Evidence/appraisal roles, supply-chain link metadata, signed provenance, verification bundles | These supply evidence vocabulary and mechanisms; emitting provenance is not a novel contribution by itself |

### Market conclusion

The implementation must not claim that confidential execution, clean rooms,
remote attestation, policy engines, output guardrails, differential privacy, or
signed provenance are new. PSBE-Runtime is best positioned as an evaluated
composition with explicit purpose semantics. Product differentiation, if any,
depends on empirical results: an immutable purpose contract binds approved data,
workload, capabilities, release, privacy, lifecycle, and reconstructable
evidence, and the benchmark tests the complete binding under attack.

## Research landscape

### Purpose limitation and usage control

Purpose-based access control predates this project. Byun's work formalized
purpose-aware access decisions, and later work developed conditional
purpose-based controls ([Purdue record](https://docs.lib.purdue.edu/ccpubs/41/)).
Distributed usage-control research addresses obligations that persist after an
initial access decision ([ACM DOI](https://doi.org/10.1145/3183342)). Biega and
Finck explain why operationalizing purpose limitation and data minimization in
data-driven systems requires meaningful system choices rather than policy text
alone ([paper](https://arxiv.org/abs/2101.06203)). Meta's PEPR account likewise
describes purpose annotations, data flows, and policy checks as an engineering
translation problem ([USENIX PEPR 2024](https://www.usenix.org/conference/pepr24/presentation/kirti)).

Therefore, neither “purpose limitation” nor “machine-readable purpose policy”
is a novelty claim.

### Confidential ML and confidential inference

Chiron protects ML-as-a-service training with SGX
([paper](https://arxiv.org/abs/1803.05961)); Slalom partitions neural inference
between trusted and untrusted computation
([ICLR paper](https://openreview.net/forum?id=rJVorjCcKQ)); Opaque protects
distributed analytics; and current CPU/GPU confidential-computing studies
measure the performance cost of protected inference
([IBM study](https://research.ibm.com/publications/securing-ai-inference-in-the-cloud-is-cpu-gpu-confidential-computing-ready)).
These systems establish that protected computation and its overhead are active,
mature research areas. A later TEE extension can change the host-trust
assumption; it cannot be presented as the origin of purpose selectivity.

### Agent security and security–utility benchmarks

[AgentDojo](https://proceedings.nips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html)
evaluates utility and prompt-injection security over 97 tasks and 629 security
test cases. [Agent Security Bench](https://openreview.net/forum?id=V4y0CpX4hK)
provides broad agent scenarios, tools, attacks, defenses, and multiple metrics.
[CaMeL](https://arxiv.org/abs/2503.18813) moves control out of the language model
with capability/data-flow enforcement and explicitly reports the resulting
utility cost. Tracked-capability research similarly applies typed capabilities
to protect secrets in agent workflows
([ACM DOI](https://doi.org/10.1145/3786335.3813127)).

Consequently, the paper must not claim to be the first to enforce agent
capabilities, isolate control from model reasoning, or measure security and
utility together.

### Privacy and finance benchmarks

[ML Privacy Meter](https://arxiv.org/abs/2007.09339) operationalizes privacy
risk assessment, while [PrivLM-Bench](https://aclanthology.org/2024.acl-long.4/)
benchmarks privacy leakage and defenses for language models. Differentially
private training is established by DP-SGD
([ACM DOI](https://doi.org/10.1145/2976749.2978318)); membership inference is an
established empirical attack
([IEEE record](https://www.computer.org/csdl/proceedings-article/sp/2017/07958568/12OmNBUAvVc)).
[FinTrust](https://aclanthology.org/2025.emnlp-main.512/) evaluates several
trustworthiness dimensions for financial language models. These works preclude
claims that privacy attacks, DP evaluation, or finance-specific trustworthy-AI
benchmarking are new in general.

## The bounded empirical gap

Within the reviewed public sources, we found no benchmark that combines all of
the following in one preregistered financial-AI experiment:

1. a confidential attribute that is intentionally useful for an approved
   financial purpose;
2. a paired counterfactual in which the same attribute is prohibited for a
   distinct legitimate purpose and only that attribute changes;
3. a fair deterministic hardened prefilter baseline with the same honest-case
   projection as the proposed runtime;
4. attacks against policy substitution, approval lifecycle, model/workload
   substitution, route fallback, tool/network capabilities, release controls,
   privacy budgets, and evidence continuity;
5. joint measurement of authorized utility retained, prohibited influence,
   silent policy compromise, evidence reconstruction, availability, privacy,
   and overhead; and
6. a component-by-component comparison of ordinary filtering with layered
   purpose-bound execution.

This is a scoped search finding, not proof that no such work exists. The paper
must state the source cutoff, search categories, and closest counterexamples.

## Candidate contribution, stated conservatively

The candidate contribution is **FinBoundBench**, a paired and attack-oriented
measurement protocol for purpose-selective financial AI, plus **PSBE-Runtime**,
a non-TEE reference implementation evaluated as one system under test. The
scientific claim is comparative and falsifiable:

> Relative to prompt-only and ungoverned baselines, does a layered purpose
> contract reduce prohibited-field influence and cross-layer compromise while
> retaining the measurable utility of the same confidential field when its use
> is approved? Does it add benefit beyond a deterministic prefilter under
> adversarial substitution and lifecycle conditions?

The implementation is not the paper's proof. Only frozen results from the
preregistered protocol can support the claim.

## Expected negative and null results

- A hardened prefilter may match PSBE projection in honest inference. That is a
  meaningful null result, not a failed benchmark.
- Prompt-only restrictions may sometimes work for a particular model/task.
- Evidence completeness may improve detectability without preventing an attack.
- DP may lower empirical leakage while lowering task utility and availability.
- Non-TEE PSBE continues to trust the host administrator and kernel.
- A TEE may reduce host trust without improving application-level purpose
  selection.

These outcomes are retained and reported; none may be rewritten as success.
