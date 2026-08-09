# Research History — FinBoundBench (protocol-v4)

This document is the authoritative lineage of the FinBoundBench research
program. It exists so that anyone reading the v4 confirmatory results can
reconstruct exactly what happened before, what was withdrawn, and what is
frozen. Versioned protocol docs live in `docs/v{2,3,4}/`; frozen artifacts
live in `results/v{2,3,4}/`; `docs/CODEX_USAGE_LOG.md` records every
automated session.

## V1 — Proof of concept (2025)

Initial framing: silent cross-purpose influence in financial AI agents.
Single-purpose demonstration harness with simulated agents. Retained only as
historical context; superseded by V2.

## V2 — Frontier matrix pilot (protocol-v2)

A live matrix over frontier models (Gemma 4 31B, Qwen3 4B, and OpenRouter
catalog snapshots) on two official public datasets (2024 HMDA D.C.; Jan 2024
CFPB complaints D.C.) with synthetic confidential fields. Delivered a
non-confirmatory matrix (1680 cells/run, two runs) labeled
`OPENROUTER_PURPOSE_SELECTIVE_MATRIX_REBUILD_NOT_CONFIRMATORY`, a
v1-preservation manifest, model manifests, and pilot/replication analyses.
V2 established the pairing methodology (variant A LOW / variant B HIGH on a
byte-identical public record) and the nondeterminism-floor concept, but its
numbers are exploratory, not confirmatory.

## V3 — Withdrawn (protocol-v3-psbe-no-tee)

V3 ran a live Gemma matrix (3360 real inferences: 1680/task) and then
**withdrew itself**:

- The v3 analysis layer was labeled
  `OPENROUTER_PURPOSE_SELECTIVE_MATRIX_REBUILD_NOT_CONFIRMATORY` with
  `confirmatoryClaimsPermitted: false`.
- Key v3 metrics were computed over **test-double streams** (simulated
  provider outputs) rather than live model outputs:
  - silent-compromise rate `57/235 = 0.2426` (test-double attack stream),
  - availability `345/350 = 0.9857` (test-double availability stream),
  - AUR `0.9341` (test-double) — formally marked **INVALID** with the rule
    "must not appear in any paper, slide, or marketing asset"
    (`docs/v3/METRIC_CORRECTION.md`).
- Eligibility findings were negative: on Task A the PSBE authorized utility
  retention was negative (≈ −0.58 … −0.91); on Task B the sensitivity gate
  failed (oracle 0.50 < baseline 0.5607). Full-record prohibited influence
  sat at or below the nondeterminism floor (`docs/v4/
  NEGATIVE_MODEL_TASK_ELIGIBILITY_RESULT.md`).

The v3 lesson encoded into v4: **a model/task configuration must pass
signal/influence/stability gates (Gates A–D) before a confirmatory benchmark
is run**, and every metric must be computed from raw live events, never from
test doubles. `results/v3/**` is immutable historical evidence and never an
input to v4 estimates.

## V4 — Eligibility redesign and confirmatory study (protocol-v4-purpose-selectivity)

V4 fixed the two v3 failure modes:

1. **Eligibility gates** (`docs/v4/ELIGIBILITY_GATES.md`,
   `src/purposebench/v4/gates.py`): admission unit = model × task; each
   candidate must pass public-only BACC range, authorized-gain, influence-
   distinguishability, and stability gates on a disjoint calibration set
   before any confirmatory call.
2. **Live-event-only metrics**: all confirmatory statistics are computed by
   `scripts/run_v4_confirmatory_statistics.py` from raw frozen event files;
   the independent recomputation (`scripts/run_v4_independent_stats.py`)
   reproduces every point estimate and confidence interval without importing
   the analysis code.

### Registered design (frozen before execution)

- Family H1–H7 (H4 and H7 report-only). Registered in
  `docs/v4/HYPOTHESES.md` and `docs/v4/CONFIRMATORY_GATEKEEPING.md`.
- Primary: deepseek/deepseek-v4-pro × hardship_support_routing, n=100 pairs
  (800 calls), power 0.95 at shrunk effect 0.167.
- Replication: moonshotai/kimi-k3 × fraud_review, n=500 pairs registered /
  120 pairs executed, power 0.825 at shrunk effect 0.063.
- Hard budget EUR 40.00; conditions A0/A1/A3/P0/P3 + ND×3 (8 calls/pair);
  A2/P2 are the deterministic HardenedPrefilter (H7, report-only).
- Pre-execution readiness: **ALL GATES PASS** (2026-08-07,
  `CONFIRMATORY_READY.md`), gate commit `7656eb7…`.

### Freezes

- Freeze 1 (`v4-confirmatory-protocol-freeze.json`, freeze_sha256
  `29242c50…`): protocol, deviation, conditions, data separation, gatekeeping,
  route policy, power analysis, dataset (240 records), eligibility results,
  signal generator, lane markers, power estimate.
- Freeze 2 (primary results, `confirmatory-primary-results-freeze.json`,
  manifest `bab5f0e2…`): deepseek-v4-pro × hardship_support_routing,
  2026-08-07.
- Freeze 3 (replication results, `confirmatory-replication-results-freeze.json`,
  manifest `c56f4dcf…`): kimi-k3 × fraud_review, 2026-08-07; binds nine
  artifact files by per-file SHA-256.
- Statistics freeze: `results/v4/statistics/confirmatory-statistical-report.json`
  (primary report sha256 `0e73a163…`; replication `4e0ce33d…`).

### Confirmatory outcome (both studies)

- Primary: 100 pairs, 1300 events, 100% availability, EUR 2.66 cost;
  authorized gain +0.39 (95% CI [0.21, 0.56], p = 0.0002); AUR 1.0;
  UIR(P0) = 1.00, UIR(P3) = 0.00 at floor 0.00; H7: P2 and P3 equivalent on
  the prohibited task.
- Replication: 120 pairs, 1560 events, 99.0% availability (16 transient
  provider failures, retained per taxonomy); authorized gain +0.108 (95% CI
  [0.033, 0.175]); AUR 1.0; floor 0.0375; UIR(P0) = 0.965, UIR(P3) = 0.0083.
- Interpretation rule 1: both studies pass their registered gates → the
  property reproduces across two model families and two tasks.
- Independent verification: 17/17 internal bundle checks
  (`results/v4/evidence/confirmatory-verification-bundle.json`) and the
  second-implementation stats crosscheck
  (`results/v4/evidence/independent-stats-crosscheck.json`) both PASS.

### Execution windows

The replication lane used execution windows 1–8 (`docs/research/
REPLICATION_WINDOW_AUDIT.md`): windows 1–2 condition-blocked (provider 403s),
3–5 empty, 6 CLI deviation (no inferential weight), 7 failed (1390/1560
failures; route `morph` unavailable), 8 accepted (1544/1560, 99.0%) under the
preregistered failure taxonomy and route policy. Admission decision recorded
2026-08-07T07:00:00Z, before any statistical analysis.

## What the confirmatory results may and may not claim

- May claim: across two model families and two tasks, the governed
  prohibited-purpose lane showed no decision influence above the independently
  measured nondeterminism floor, while the authorized lane retained the
  measured authorized utility gain; all estimates independently recomputed.
- May NOT claim (per `docs/LIMITATIONS.md` and the statistical plan's
  result-language rules): "proved secure", "eliminates influence", "complies
  with GDPR", "universal", "production-ready". P2 ≈ P3 on the replication
  task means a deterministic prefilter can match the governed path on narrow
  field removal; the paper does not claim superiority there. H4
  (cross-layer compromise) is NOT TESTABLE in the confirmatory study. No TEE
  execution occurred (requires separate authorization, Phase 13).
