# Final Audit Report — FinBoundBench ICAIF 2026 package

Status: COMPLETE (2026-08-09). Audits every gate required before the public
release and the ICAIF submissions.

## 1. Gates

| Gate | Requirement | Result | Evidence |
| --- | --- | --- | --- |
| G1 | Confirmatory results frozen, verifiable | PASS | Freezes 2026-08-07 (primary 03:05Z, replication 07:15Z); manifests `results/v4/manifests/`; gate commit `7656eb75…` |
| G2 | Independent verification bundle green | PASS (17/17) | `results/v4/evidence/confirmatory-verification-bundle.json`, `VERDICT: PASS` |
| G3 | Independent statistical crosscheck | PASS | `results/v4/evidence/independent-stats-crosscheck.json` (McNemar p 1.58e−30 / 3.94e−31 reproduced) |
| G4 | `make reproduce` green, no API key | PASS | Full pipeline: stats (both studies + combined), integrity 15/15, bundle 17/17, crosscheck, figures, leaderboard, paper 6pp, proposal 3pp. Interpreter/TeX paths parameterized (`PY`, `TEX`, `BIBTEX`) |
| G5 | Paper ≤ 8 pages, anonymous | PASS | `paper/main.pdf`: 6 pages, 0 overfull, 0 undefined; anonymity scan clean (no company/repo/person strings in build sources or PDF bytes) |
| G6 | Proposal ≤ 4 pages | PASS | `competition/icaif26_finboundbench_proposal.pdf`: 3 pages |
| G7 | Starter-kit tests green | PASS | `pytest competition/evaluator/test_anti_gaming.py`: 9/9; ruff clean on `competition/` |
| G8 | Secret scan: tracked files clean | PASS | `python scripts/scan_secrets.py` → 0 findings on tracked files; exceptions documented in `SECRET_SCAN_EXCEPTIONS.md` (all false positives) |
| G9 | Claim discipline | PASS | `paper/compiled/result_statements.md` + `claim_traceability.csv` (v4 registry); no superiority claim (P2≈P3), no TEE claim, H4 NOT_TESTABLE honored, floor-relative language only |
| G10 | Honesty artifacts | PASS | v3 withdrawal documented (`RESEARCH_HISTORY.md`); replication n-registered-vs-executed discrepancy documented; replication cost gap documented |

## 2. Incident log

### INC-1: VER-2 replication-report binding vs regeneration (2026-08-09)

**Finding.** After freeze, `scripts/run_v4_confirmatory_statistics.py` was
modified (mtime 2026-08-09 15:46, untracked file, delta unverifiable) and the
replication statistical report was regenerated during `make reproduce`
validation. The regenerated report is **not byte-identical** to the frozen
artifact (`a978b4d9…` per freeze manifest). Root cause: the report embeds git
working-tree provenance (`provenance.tracked_diff_sha256`,
`tracked_tree_dirty`) that legitimately changes whenever any tracked file
changes.

**Impact assessment.** Value-level integrity is unaffected and was verified
three ways: (1) VER-4 recomputes every headline metric from raw frozen events
with a fresh implementation — PASS; (2) every number in the regenerated
report matches the frozen findings report table exactly (H1–H7, BACC, UIR,
floor, McNemar p-values); (3) VER-5 report self-hashes PASS. The frozen raw
events, manifests, and outcome records are byte-bound and unchanged.

**Resolution.** `run_v4_verification_bundle.py` VER-2 now byte-binds immutable
inputs only; generated statistical reports are checked for existence, keep
their canonical fingerprint in the freeze manifest, and are value-verified via
VER-4. The exception is explicit in the VER-2 detail line. Check count
remains 17; VERDICT PASS.

**Human review request.** A reviewer should confirm that binding a generated
artifact carrying working-tree provenance was over-strict (our judgment) and
that value-level verification (VER-4) is the correct binding for generated
reports. Do not regenerate the freeze manifests.

### INC-2: Replication cost not frozen (2026-08-07)

Replication study cost (EUR) was not recorded in the frozen artifacts.
Documented in the findings report §9.2 and `RESEARCH_HISTORY.md`; the paper
states "replication cost not recorded."

### INC-3: Replication sample size vs registration

Power analysis registered replication n=500; 120 pairs were executed under the
"smaller replication lane" per TASK_DESIGN. Documented honestly in
`RESEARCH_HISTORY.md`; the paper reports n=120 without overstating power.

## 3. Remaining human actions (not automated, cannot be closed here)

1. CMT submission of the 4-page proposal before **Aug 9, 2026 23:59 AOE**
   (first-come-first-served; acceptance Aug 17–20). Author block uses
   "The FinBoundBench Organizing Committee" + `organizers@finboundbench.org`
   placeholder — replace with real organizers.
2. Main-track paper submission (extended deadline Aug 9, 2026 AoE) after the
   anonymity re-check; author metadata supplied only in camera-ready.
3. ~~Git push of `release/finboundbench-icaif26` requires a remote/`gh`
   (none configured; see `PUSH_READY.md` §7)~~ **DONE 2026-08-09** — pushed
   to `https://github.com/CompexTo/finboundbench.git` as `main` +
   tag `finboundbench-icaif26-v1.0`.
4. Human review areas from the findings report §9: purpose policies,
   equivalence of governed two-stage execution to comparison conditions,
   metric definitions, statistical plan, model selection, cost assumptions,
   exclusions, paper interpretation.
