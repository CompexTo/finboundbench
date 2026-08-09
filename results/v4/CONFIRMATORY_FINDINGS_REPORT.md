# v4 Confirmatory Launch — Full Findings Report

**Protocol:** `protocol-v4-purposebench` (purpose-selectivity benchmark, v4)
**Launch:** Confirmatory phase — primary study + replication study
**Frozen:** 2026-08-07 (primary results freeze `03:05Z`, replication results freeze `07:15Z`)
**Verification bundle:** `results/v4/evidence/confirmatory-verification-bundle.json` — **VERDICT: PASS (17/17 checks)**
**Combined interpretation rule 1:** *Both studies pass → the effect reproduces across two model families and two financial tasks.*

> Status: internal benchmark results. Human review of protocol, analysis, model
> selection and interpretation required before any external claim (see
> `CONTRACT_V4.md`, `docs/CODEX_USAGE_LOG.md`).

---

## 1. Executive summary

The v4 confirmatory phase tested whether **prohibited visible data (P0)**
influences model decisions above the natural-decision floor (ND), while
masking variants (P2, P3) suppress that influence, and whether the governed
execution context (A1, A3) raises decision accuracy.

Both studies passed every pre-registered gate in the fixed-sequence chains:

- **Chain 1 (authorized utility):** H1 (gain) PASS, H2 (AUR) PASS
- **Chain 2 (prohibited influence):** H3 (net UI > 0) PASS, H5 (suppression) PASS, H6 (floor equivalence) PASS
- **Exploratory:** H4 NOT_TESTABLE (P1 not in the registered minimal condition set), H7 EQUIVALENT (P2 = P3)

The findings hold across two different model families and two different
financial tasks (primary: deepseek-v4-pro on hardship-support routing;
replication: Kimi K3 on fraud review).

---

## 2. Design recap

| Element | Primary study | Replication study |
|---|---|---|
| Lane (model) | `deepseek-deepseek-v4-pro` | `moonshotai-kimi-k3` |
| Task | `hardship_support_routing` | `fraud_review` |
| Execution window | `primary-window-2` | `replication-window-8` |
| Paired cases | 100 pairs | 120 pairs |
| Calls per pair | 8 (A0, A1, A3, P0, P3, ND + ND×3 repetitions) | 8 |
| Total raw events | 1,300 | 1,560 |
| Provider success | 1,300 / 1,300 (100.0%) | 1,544 / 1,560 (99.0%) |
| Cost (EUR) | 2.6636 | not recorded in frozen artifacts |
| Seed | `20251004` | `20251004` |

Conditions (per `docs/v4/CONFIRMATORY_POWER_ANALYSIS.md` §5 minimal set):
- **A0** — no purpose, no metadata, no context (baseline)
- **A1** — full purpose (+ metadata + context), non-gated
- **A3** — Compex-governed execution (purpose gating, evidence chain, audit)
- **P0** — prohibited visible data (e.g., account balance / flagged flag) mixed into the prompt
- **P2** — prohibited data masked (deterministic)
- **P3** — prohibited data masked with declared purpose (partial)
- **ND** — natural-decision floor: identical visible input repeated ND×3

Replication window history: `w1..w6` failed, `w7` failed; `w8` accepted with
registered failure handling (`ACCEPTED_WITH_REGISTERED_FAILURE_HANDLING`).
16 transient failures in w8 (14 `PROVIDER_TRANSPORT_ERROR`, 2
`PROVIDER_TIMEOUT`) excluded per `PROVIDER_FAILURE_TAXONOMY`; per-condition
complete pairs: A0=119, A1=120, A3=118, P0=113, P3=120, ND=120; 114 pairs
complete on all six conditions.

---

## 3. Primary study results (`deepseek-v4-pro` / hardship routing)

Sample: 100 pairs, 1,300 events, 100% provider success.

| Metric | Value |
|---|---|
| BACC A0 (no purpose) | 0.32 |
| BACC A1 (full purpose) | 0.71 |
| BACC A3 (governed) | 0.71 |
| UIR P0 (prohibited visible) | 1.00 |
| UIR P2 (masked, deterministic) | 0.00 |
| UIR P3 (masked + purpose) | 0.00 |
| ND floor | 0.00 |

| Hypothesis | Decision | Point estimate | 95% CI | p (one-sided) |
|---|---|---|---|---|
| H1 gain (A1 − A0) | **PASS** | 0.39 | [0.21, 0.56] | 0.00020 |
| H2 AUR retention (gain → gov) | **PASS** | AUR 1.0 | [1.0, 1.0] | — |
| H3 net UI (P0 − ND) | **PASS** | 1.00 | [1.00, 1.00] | 0.00020 |
| H5 P2/P3 suppression | **PASS** | −1.00 both | [−1.0, −1.0] | 0.0 |
| H6 P3 vs floor (margin 0.05) | **PASS** | −0.00 | [0.0, 0.0] | 0.0 |
| H7 P2 = P3 (TOST) | EQUIVALENT | 0.00 | — | p_TOST 0.0 |

H3 McNemar (exact): 100 discordant pairs, 100 A-only, p = 1.58e−30.

---

## 4. Replication study results (`Kimi K3` / fraud review)

Sample: 120 pairs, 1,560 events, 99.0% provider success (16 transient
failures excluded under the registered taxonomy).

| Metric | Value |
|---|---|
| BACC A0 | 0.625 |
| BACC A1 | 0.7333 |
| BACC A3 | 0.7333 |
| UIR P0 | 0.9646 |
| UIR P2 | 0.00 |
| UIR P3 | 0.0083 |
| ND floor | 0.0375 |

| Hypothesis | Decision | Point estimate | 95% CI | p (one-sided) |
|---|---|---|---|---|
| H1 gain (A1 − A0) | **PASS** | 0.1083 | [0.033, 0.175] | 0.00200 |
| H2 AUR retention | **PASS** | AUR 1.0 | [1.0, 1.0] | — |
| H3 net UI (P0 − ND) | **PASS** | 0.9292 | [0.8805, 0.9646] | 0.00020 |
| H5 P2/P3 suppression | **PASS** | −0.9646 / −0.9558 | ≤ [−0.9115, −0.9912] | 0.0 |
| H6 P3 vs floor (margin 0.05) | **PASS** | −0.0292 | [−0.0625, 0.0] | 0.0236 |
| H7 P2 = P3 (TOST) | EQUIVALENT | −0.0083 | — | p_TOST 9.98e−07 |

H3 McNemar (exact): 113 pairs, 102 A-only, 7 both, 4 neither, p = 3.94e−31.

---

## 5. Combined interpretation

`confirmatory-statistical-report.json` (sha `report_sha256` in artifact):

```json
"interpretation": {
  "rule": 1,
  "text": "Both studies pass -> reproduced across two model families and two financial tasks."
}
"combined_claims": {
  "both_studies_pass": true,
  "primary_chain_1_authorized":   "PASS,PASS",
  "primary_chain_2_prohibited":   "PASS,PASS,PASS",
  "replication_chain_1_authorized": "PASS,PASS",
  "replication_chain_2_prohibited": "PASS,PASS,PASS"
}
```

Key qualitative findings:

1. **Prohibited visible data strongly and significantly alters decisions**
   (P0 UIR ≈ 1.0 and 0.96, both far above the ND floor 0.0 / 0.0375).
2. **Masking suppresses the influence entirely**: P2 and P3 UIR ≈ 0 in both
   studies; P2 ≡ P3 (equivalence, TOST delta 0.05).
3. **Declaring purpose improves routing accuracy**: A1 − A0 gain 0.39
   (primary) and 0.108 (replication), both significant with CI strictly > 0.
4. **The governed execution context retains the full authorized gain**
   (AUR = 1.0 in both studies: BACC A3 = BACC A1).
5. **No residual P3 effect above floor**: H6 passes in both studies; the
   primary study shows exact 0, the replication study −0.0292 within the
   0.05 margin.

---

## 6. Independent verification bundle

`results/v4/evidence/confirmatory-verification-bundle.json`
Verifier: `scripts/run_v4_verification_bundle.py` (fresh implementation;
recomputes headline metrics from raw frozen events without importing the
statistics script). **VERDICT: PASS — 17/17 checks.**

| Check | Scope | Result |
|---|---|---|
| VER-1 ×6 | Freeze manifest self-hash round-trips (protocol, dataset, primary results, replication results, eligibility, signal) | PASS |
| VER-2 ×3 | Content SHA-256 of every manifest-bound file (12 + 5 + 9 files) | PASS |
| VER-3 ×2 | Event accounting: counts, pairs, provider success match outcome records | PASS |
| VER-4 ×2 | Independent recomputation of BACC / UIR / ND floor / gain / net-UI from raw events matches the reports exactly | PASS |
| VER-5 ×3 | Report self-hashes (primary, replication, combined) | PASS |
| VER-6 ×1 | Combined chain decisions consistent with per-study reports; interpretation rule 1 consistent | PASS |

Freeze integrity (`scripts/run_v4_confirmatory_integrity.py`) previously
verified INV-1..INV-7 (budget, mock-run absence, event immutability, etc.)
for the confirmatory run.

---

## 7. Freeze manifest index

| Freeze | File | Self-hash (SHA-256) | Contents |
|---|---|---|---|
| Protocol | `results/v4/manifests/v4-confirmatory-protocol-freeze.json` | `b1dceeec…7c85` | 12 bound files (protocol, specs, conditions, power analysis, gatekeeping) |
| Dataset | `results/v4/manifests/confirmatory-dataset-freeze.json` | `e7f443ef…d5f` | v4 dataset records with per-record hashes |
| Primary results (freeze 2) | `results/v4/manifests/confirmatory-primary-results-freeze.json` | `bab5f0e2…4e3f` | 5 bound files; 1,300 events, 100 pairs, cost €2.6636 |
| Replication results (freeze 3) | `results/v4/manifests/confirmatory-replication-results-freeze.json` | `c56f4dcf…94c2` | 9 bound files (per-file hashes); window acceptance record |
| Eligibility results | `results/v4/manifests/eligibility-results-freeze.json` | `bd6d2fb5…449b` | per-lane/task eligibility gates, negative evidence |
| Signal | `results/v4/manifests/v4-signal-freeze.json` | `f90b545e…999` | signal-strength calibration values |

---

## 8. Where everything lives

| Artifact | Path |
|---|---|
| Full findings (this file) | `results/v4/CONFIRMATORY_FINDINGS_REPORT.md` |
| Combined statistical report | `results/v4/statistics/confirmatory-statistical-report.json` |
| Primary report | `results/v4/statistics/primary-statistical-report.json` |
| Replication report | `results/v4/statistics/replication-statistical-report.json` |
| Verification bundle | `results/v4/evidence/confirmatory-verification-bundle.json` |
| Raw primary events (frozen) | `results/v4/confirmatory/primary-window-2/deepseek-deepseek-v4-pro/hardship_support_routing/events.jsonl` |
| Raw replication events (frozen) | `results/v4/confirmatory/replication-window-8/moonshotai-kimi-k3/fraud_review/events.jsonl` |
| Deterministic P2 events | `…/{primary-window-2,replication-window-8}-deterministic-p2/…/events.jsonl` |
| Window outcome records | `results/v4/confirmatory/{primary-window-2,replication-window-8}-outcome.json` |
| Freezes | `results/v4/manifests/*.json` |
| Protocol + specs | `docs/v4/PROTOCOL-v4-purpose-selectivity.md`, `docs/v4/CONFIRMATORY_POWER_ANALYSIS.md`, `docs/v4/CONFIRMATORY_GATEKEEPING.md` |
| Analysis scripts | `scripts/run_v4_confirmatory_statistics.py`, `scripts/run_v4_confirmatory_integrity.py`, `scripts/run_v4_verification_bundle.py` |
| Session/agent log | `docs/CODEX_USAGE_LOG.md` |

---

## 9. Caveats and review areas (human)

1. **Internal verification only.** The bundle is an automated cross-check;
   external independent verification is gated on authorization
   (`CONTRACT_V4.md`).
2. **Replication cost not recorded** in frozen artifacts (primary: €2.6636).
3. **H4 not testable** by design: P1 was not part of the registered minimal
   condition set; no P1 events exist.
4. Replication window w8 required 7 windows of attempts; transient failure
   handling follows the registered taxonomy.
5. Review areas required before external claims: purpose policies,
   equivalence of Compex two-stage execution to comparison conditions, metric
   definitions, statistical plan, model selection, cost assumptions,
   exclusions, paper interpretation.
