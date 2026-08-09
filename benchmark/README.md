# Benchmark — frozen protocol and data access

This directory holds the frozen v4 protocol documents and the data access
story for FinBoundBench.

## Frozen protocol documents

These files were frozen (content-addressed) before any confirmatory execution
and are bound in `results/v4/manifests/v4-confirmatory-protocol-freeze.json`:

- `PROTOCOL-v4-purpose-selectivity.md` — the protocol (conditions, metrics,
  gatekeeping, failure taxonomy, budget, routing policy).
- `CONFIRMATORY_POWER_ANALYSIS.md` — sample sizes, effect assumptions, and the
  registered minimal condition set.
- `CONFIRMATORY_GATEKEEPING.md` — fixed-sequence gate chains (H1→H2,
  H3→H5→H6), H7 report-only, H4 NOT_TESTABLE.
- `CONDITION_IMPLEMENTATIONS.md` — exact per-condition rendering semantics
  (which fields are transmitted, masked, or annotated).

Originals live in `docs/v4/`; the copies here are the release surface. The
frozen manifests, statistics, findings report, and evidence bundle live in
`results/v4/` (see `results/v4/README.md` there if present).

## Data

- `data/v4/v4_signal_manifest.json` — per-signal definitions (authorized and
  prohibited actions, label rule, sensitivity gates).
- `data/v4/v4_targets.csv` — public-feature scoring coefficients and seeds
  used to synthesize ground truth (Equation y = g(x) + beta*z + eps).
- `data/v4/v4_calibr/pairs.jsonl` — dev split (harness development, figures).
- `data/v4/v4_confirm/pairs.jsonl` — confirmatory split (locked by the
  dataset freeze; used for all reported tests).

No raw official CSVs are committed. The source datasets are public:

- HMDA 2024, District of Columbia:
  https://ffiec.cfpb.gov/data-publication/
- CFPB Consumer Complaints, January 2024, District of Columbia:
  https://www.consumerfinance.gov/data-research/consumer-complaints/

`scripts/fetch_v4_sources.py` downloads and extracts the exact records used
(documented in the script). The confidential fields in the pairs files are
synthetic (`SYNTHETIC_*`) and are not present in the source records.
