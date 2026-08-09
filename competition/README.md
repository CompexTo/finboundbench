# FinBoundBench Challenge

**Authorized to Use, Forbidden to Influence** — Benchmarking Purpose-Selective
AI in Financial Decision Systems. ICAIF 2026 competition track proposal.

## Documents

- `icaif26_finboundbench_proposal.tex` + `.pdf` — the 4-page competition
  proposal (compiles with the vendored `acmart.cls`; 3 pages, within the
  4-page limit)
- `rules.md` — normative challenge rules (tracks, conditions, scoring,
  leaderboard, anti-gaming, integrity, timeline)
- `STARTER_KIT.md` — participant-facing getting-started guide
- `submission_schema.json` — normative submission contract
- `evaluator/` — official evaluation harness (independent implementation;
  no imports from `src/purposebench`)
- `baselines/` — seven degenerate strategies + dev-only oracle
- `sample_submission/` — minimal valid Track A submission (no API key)
- `results/leaderboard_dev.*` — regenerated reference leaderboard

## Reproduce

```bash
python -m pip install -e .[dev]
make starter-kit          # regenerates competition/results/leaderboard_dev.*
python -m pytest competition/evaluator/test_anti_gaming.py -q
```

## Compile the proposal

```bash
pdflatex icaif26_finboundbench_proposal
bibtex icaif26_finboundbench_proposal
pdflatex icaif26_finboundbench_proposal
pdflatex icaif26_finboundbench_proposal
```

The ACM class files (`acmart.cls`, `ACM-Reference-Format.bst`, and the
`*.bbx`/`*.cbx`/`*.dbx` companions) are vendored here so the proposal
compiles offline. `acmart.cls` is ACM's v2.19 (2026-06-27) generated from its
dtx; see `LICENSE` in the ACM distribution for terms.
