# Reproducibility

This repository ships frozen confirmatory evidence and the exact tooling to
regenerate every number, figure, and PDF from the raw events. No API key is
required for any reproducibility step.

## Quick start

```bash
make reproduce          # full pipeline, no API key (see below)
```

The pipeline runs, in order:

1. `scripts/run_v4_confirmatory_statistics.py --study primary` — regenerates
   the primary statistical report from frozen raw events (seeded bootstrap,
   deterministic).
2. `scripts/run_v4_confirmatory_statistics.py --study replication` — same for
   the replication study.
3. `scripts/run_v4_confirmatory_statistics.py --combine` — combined
   interpretation (rule 1).
4. `scripts/run_v4_confirmatory_integrity.py` — freeze-chain and budget
   integrity checks (15/15).
5. `scripts/run_v4_verification_bundle.py` — independent verification bundle,
   17/17 checks (fresh implementation over raw events; does not import the
   statistics scripts).
6. `scripts/run_v4_independent_stats.py` — independent statistical crosscheck
   (McNemar exact p-values etc.).
7. `scripts/run_v4_headline_figure.py` and
   `scripts/make_paper_figure_schematic.py` — figures from frozen data only.
8. `make starter-kit` — regenerates the competition dev leaderboard from the
   dev split (deterministic harness, 9/9 anti-gaming tests).
9. `make paper` / `make proposal` — compiles the paper and proposal PDFs.

Expected output: `VERDICT: PASS` for the verification bundle, PASS on every
gate, `main.pdf` (6 pages) and `icaif26_finboundbench_proposal.pdf` (3 pages).

## Re-running live experiments (optional, requires a key)

```bash
make rerun-live OPENROUTER_API_KEY=<key>   # not provided; see below
```

There is no single `rerun-live` target: live execution in v4 was driven by the
governed bridge (`scripts/governed_openrouter_bridge_v4.cjs`) and the
eligibility runner (`src/purposebench/v4/eligibility_runner.py`), with windows
selected via the registered route policy (`docs/v4/`). Any re-execution
produces **EXPLORATORY** results that must never overwrite the frozen
confirmatory artifacts (`results/v4/confirmatory/`); the freeze manifests and
the verification bundle are the authority.

## Determinism and provenance

- Random generators are seeded (`SEED = 20251004`; per-hypothesis
  `SEED * 1000 + n`); statistical reports regenerate byte-identically on a
  fixed working tree.
- Statistical reports embed git provenance (commit, tracked-diff hash) as a
  reproducibility record. Because the tracked-diff hash changes with any
  tracked-file edit, regenerated reports may differ byte-wise from the frozen
  artifacts; their **values** are independently re-verified (VER-4) and their
  canonical fingerprints stay in the freeze manifests. See
  `docs/research/FINAL_AUDIT_REPORT.md` INC-1.
- All frozen inputs (events, manifests, outcome records, dataset, eligibility)
  are content-addressed (SHA-256) and byte-bound by
  `scripts/run_v4_verification_bundle.py` (VER-1/VER-2).

## Toolchain

- Python 3.11+; `pip install -e .[dev]` (numpy, pandas, statsmodels, scipy,
  pytest, ruff, matplotlib).
- LaTeX: any TeX distribution with the `acmart` class (v2.x) and `booktabs`;
  the exact `acmart.cls`/`ACM-Reference-Format.bst` used for the released PDFs
  are vendored in `competition/` and `paper/`. The Makefile accepts
  `TEX`/`BIBTEX` overrides.
- The Makefile is interpreter-agnostic: override `PY` if `python` is not your
  venv (e.g. `make reproduce PY=.venv/Scripts/python.exe`).
