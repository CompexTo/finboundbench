# Changelog

All dates are 2026. This log covers the public release surface; internal
history (v1–v3) is documented in `docs/research/RESEARCH_HISTORY.md`.

## v1.0 — 2026-08-09 (release candidate `finboundbench-icaif26-v1.0`)

### Added
- **Competition package**: ICAIF 2026 competition-track proposal (3 pp),
  complete starter kit (evaluator harness, 7 degenerate baselines + dev-only
  oracle, sample submission, submission schema, rules, container spec),
  validated dev leaderboard.
- **Paper**: anonymous 8-page-limit paper (6 pp, 2 figures) reporting the v4
  confirmatory study; result-statement registry and claim-traceability CSV
  regenerated for v4.
- **Verification tooling**: `make reproduce` (no API key), `make paper`,
  `make proposal`, `make starter-kit`; interpreter/TeX parameterization
  (`PY`, `TEX`, `BIBTEX`).
- **Docs**: `REPRODUCIBILITY.md`, `RELEASE_NOTES.md`, `CITATION.cff`;
  `docs/research/`: research history, literature/novelty audit, secret-scan
  reports, window audit, push-ready plan, final audit, submission metadata,
  final checklist, executive summary.

### Changed
- `paper/main.tex` + sections: rewritten from the v3-era draft to the v4
  confirmatory study (title "Authorized to Use, Forbidden to Influence";
  abstract, claims, tables, and figures bound to frozen results).
- `paper/compiled/` and `paper/generated/`: stale v3 tex snapshots purged;
  registries regenerated for v4.
- `Makefile`: added `reproduce`, `paper`, `proposal` targets; all recipes use
  `$(PY)`.
- `pyproject.toml`: pytest `pythonpath = ["src", "."]`.

### Fixed
- `scripts/run_v4_verification_bundle.py`: VER-2 now byte-binds immutable
  inputs and value-verifies generated statistical reports (their embedded
  git-tree provenance made byte-binding over-strict); exception explicit in
  the check detail (see `docs/research/FINAL_AUDIT_REPORT.md` INC-1).

## Earlier history (not part of this release surface)

- **v4 confirmatory study** (2026-08-07): protocol freeze, eligibility gates,
  primary + replication studies, results freeze, 17/17 verification.
- **v3** (withdrawn protocol; test-double metrics invalid for live claims).
- **v2 / v1** (exploratory; non-confirmatory).
