# Literature and Novelty Audit — FinBoundBench / Purpose-Selective AI

Audit date: 2026-08-09. Scope: closest scholarly and regulatory work to the
FinBoundBench claims: purpose-selective execution (PSBE), the FinBoundBench
benchmark, and the joint measurement of authorized utility retention and
excess unauthorized influence relative to a nondeterminism floor.

Search covered: ACM Digital Library, IEEE, USENIX, ACL, NeurIPS/ICML/ICLR
(OpenReview), arXiv, PMLR, and legal/regulatory sources (GDPR Art. 5, EU AI
Act, ICO guidance). Concepts searched: purpose limitation AI/LLM, purpose
binding, purpose-based access control, contextual integrity + ML, AI
governance runtime, information flow control + ML, data minimization in ML,
LLM sensitive-attribute influence, counterfactual fairness, privacy leakage
benchmarks, policy enforcement for LLM, purpose-bound privacy.

---

## 1. Close work — comparison table

| Work | What it studies | Controls access? | Tests purpose? | Same field authorized in one purpose, prohibited in another? | Authorized utility measured? | Unauthorized influence measured? | Nondeterminism floor measured? | Execution evidence bound? | Overlap with FinBoundBench | Remaining distinction |
|---|---|---|---|---|---|---|---|---|---|---|
| Byun, Bertino & Li, *Purpose-Based Access Control for Privacy Protection in Relational Databases*, SACMAT'05 / VLDBJ 17(3) 2008, DOI 10.1007/s00778-006-0023-0 | Purpose-based access control (PBAC) for databases: allowed/prohibited/conditional purposes per data element, query modification | Yes (query-level projection) | Yes (access purposes vs intended purposes) | Yes — the model explicitly supports "may be used for purpose A, must not be used for purpose B" | No (no decision task) | No | No | No | Concept of allowed/prohibited purposes per data element | DB access-control model; no model behavior, no influence measurement, no utility retention, no statistical methodology |
| Tiwari et al., *Information Flow Control in Machine Learning through Modular Model Architecture*, USENIX Security 2024 (arXiv:2306.03235) | Non-interference (NI) formalized for ML; Mixture-of-Experts architecture confines training-data influence per security domain | Yes (inference-time expert routing per access policy) | Partially (security domains, not financial purposes) | Yes at training-data level (domain inclusion/exclusion) | Yes (accuracy of the IFC model vs baseline) | Yes (NI violation = influence) | No (deterministic framing; probabilistic NI discussed only theoretically) | No | Formalizes "same data must not influence here, may there" for ML | Architecture proposal, not a benchmark; training-data domains, not prompt-level confidential fields; no measurement methodology, no replication |
| Hu et al., *ToolPrivacyBench: Benchmarking Purpose-Bound Privacy in Tool-Using LLM Agents*, arXiv:2606.28061, 2026 | Whether tool-using agents transmit private atoms only to authorized tools/sinks ("need-to-know"); trajectory audit vs policy knowledge base | Audits transmission (arguments + audit logs) | Yes ("purpose-bound privacy"; allowed/forbidden field-tool relations) | Yes — same private atom necessary for one tool, forbidden for another | Partial (task success/conveyance) | Yes (over-disclosure rate FOR/SWLR/MT-POI) | No | Partially (backend audit logs) | Closest conceptual sibling: purpose-bound data use for LLM systems; policy knowledge base with authorization matrix | Measures **transmission/disclosure** in tool arguments, not **decision influence**; no counterfactual paired design; no independent nondeterminism floor; no statistical inference; no utility-retention-vs-influence joint evaluation; single-domain (agents) |
| Fu et al. (Microsoft), *CI-Work: Benchmarking Contextual Integrity in Enterprise LLM Agents*, ACL 2026 Industry (also "Benchmarking Contextual Integrity in Enterprise LLM Agents") | CI-grounded leakage/violation/conveyance metrics for enterprise agents | Evaluates disclosure, not control | Yes (CI norms, information-flow contexts) | Partially (sensitive entries vs needed entries per task) | Partial (conveyance) | Yes (leakage/violation rates) | No | No | Measures both necessary-info conveyance and sensitive disclosure | Action-level disclosure of sensitive entries, not decision influence of a confidential field; no purpose-pair counterfactual; no floor; no utility retention ratio |
| Mireshghallah et al., *Can LLMs Keep a Secret? (CONFAIDE)*, ICLR 2024 | Tiered evaluation of LLM privacy reasoning via contextual integrity | No | Yes (contextual norms) | Partially (tier 4 contextual reasoning) | No | Yes (disclosure judgments) | No | No | Privacy reasoning benchmarks for LLMs | Judgment tasks, not decision systems; no same-signal-two-purpose design; no behavioral measurement |
| Li & Hu, *PrivaCI-Bench*, arXiv:2502.17041, 2025 | CI + legal-compliance privacy evaluation of LLMs (court cases, policies, synthetic vignettes) | No | Yes (CI norms + regulations) | Partially | No | Yes (compliance classification) | No | No | Privacy evaluation benchmarks | Legal reasoning classification, not decision influence; no confidential-signal counterfactual; no floor |
| Hu & Zhao, *Fin-Bias: Evaluating LLM Decision-Making under Human Bias in Finance*, arXiv:2605.09106, 2026 | Whether LLM investment decisions herd on analyst ratings; removes/replaces the rating sentence and measures decision change (herding score) | No | No (bias, not purpose) | No | No (utility vs ground truth not central) | Yes — **variant-based decision-influence measurement** | No | No | **Methodologically closest**: counterfactual perturbation of one context element → decision-change rate | Studies herding/bias, not data governance; no authorized/prohibited purposes; no utility-retention framing; no nondeterminism floor; no evidence binding |
| Kusner et al., *Counterfactual Fairness*, NeurIPS 2017 | Decisions invariant under counterfactual changes of protected attributes (causal model) | No | No (fairness, not purpose) | No | No | Yes (counterfactual decision comparison) | No | No | Counterfactual decision-distribution comparison | Fairness auditing of models; requires causal models; no governance contract, no utility-retention trade-off axis, no real-system benchmark |
| Wang, Sridhar & Blei, *Adjusting ML Decisions for Equal Counterfactual Opportunity* (2023) | Adjust decisions so counterfactual decision distributions are equal across protected attribute | No | No | No | No | Yes | No | No | Same family as counterfactual fairness | Fairness adjustment; not purpose governance |
| CI theory: Nissenbaum, *Privacy in Context* (2010); Barth, Datta, Mitchell, Nissenbaum, S&P 2006 | Privacy as context-appropriate information flows (CI norms) | Conceptual | Yes | Yes — flow norms are purpose/context-relative | N/A | N/A | N/A | N/A | Theoretical foundation for purpose-relative data use | No implementation or measurement; we operationalize purpose-relative use for decision systems |
| GDPR Art. 5(1)(b)-(c), EU AI Act; AI Now "Data Minimization as a Tool for AI Accountability" (2021); ICO "Guidance on AI and data protection" | Legal principles: purpose limitation, data minimization for AI | Legal | Yes | Yes (regulatory) | N/A | N/A | N/A | N/A | Motivates the benchmark | Regulatory principles without operational benchmark; no influence measurement |

Also reviewed but less central: InvestorBench (ACL 2025, financial LLM-agent tasks — no privacy axis), Fin-Bias-adjacent financial bias audits, "Empowering Many, Biasing a Few" (credit-scoring LLMs — fairness, not purpose governance), IFC literature (Goguen & Meseguer 1982 non-interference), policy-based access control (Ping Identity; usage control, Sandhu & Park).

---

## 2. Terminology check

- "Purpose-based access control" (Byun et al.) — established term for DB access control. We do **not** reuse it; our scope is decision-system behavior.
- "Purpose-bound privacy" — used by ToolPrivacyBench (2026) for transmission-bound disclosure in tool agents. We use **purpose-selective execution (PSBE)** to denote the behavioral property (use when authorized, no influence when prohibited) plus the governed execution contract; the benchmark is **FinBoundBench**. Our "purpose-selective" phrasing does not conflict with a prior established term in the searched literature.
- "Contextual integrity" (Nissenbaum) — we position PSBE as an operationalization of purpose-relative informational norms for financial decision systems, citing CI rather than claiming CI as novelty.

---

## 3. Novelty verdict

The proposed contribution is validated against the audit:

> **A benchmark methodology that jointly measures (a) authorized-utility retention
> and (b) excess unauthorized influence relative to an independently measured
> nondeterminism floor, using the same confidential signal across allowed and
> prohibited financial purposes, with frozen preregistered analysis and
> hash-bound evidence.**

Every component exists separately somewhere (PBAC purposes; IFC non-interference;
CI norms; Fin-Bias-style influence perturbation; leakage benchmarks), but no
located work jointly:

1. uses the **same confidential field** in an authorized and a prohibited
   financial purpose for the **same underlying case** (counterfactual purpose
   pairing);
2. measures **authorized utility retention** (governed vs authorized vs
   public-only) on real LLM decision systems;
3. measures **prohibited-purpose influence as decision-change rate relative to
   an independently measured identical-input nondeterminism floor** (so
   model noise is not counted as data influence);
4. preregisters the analysis, freezes raw events + manifests, and ships an
   independent recomputation.

Closest single work (ToolPrivacyBench) measures transmission disclosure in
tool trajectories without the decision-influence/floor/utility framing; closest
method (Fin-Bias) measures context-element influence on decisions but has no
purpose-governance or utility-retention dimension.

**Claim discipline:** the paper claims only the four properties above; it does
not claim to invent "purpose limitation" or "contextual integrity"; it cites
PBAC, IFC-ML, CI, Fin-Bias, ToolPrivacyBench, and GDPR/AI Act, and narrows the
contribution to the joint measurement methodology and its frozen evidence.

---

## 4. Recommended framing adjustments (from audit)

- Related Work must cite ToolPrivacyBench prominently and state the
  transmission-vs-influence distinction explicitly (the "not a column filter"
  caveat extends to "not a transmission auditor").
- Cite Fin-Bias for the perturbation-based influence methodology lineage.
- Cite Byun et al. for purpose authorization lineage and state that PSBE adds
  decision-level influence measurement + evidence binding beyond DB access.
- Do not claim novelty for "purpose matters in data governance" — claim
  novelty for the joint measurement methodology and the frozen evidence.
