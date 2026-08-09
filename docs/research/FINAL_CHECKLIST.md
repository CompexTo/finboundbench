# Final Checklist — FinBoundBench ICAIF 2026 package

Status: OPEN. Items marked [x] are verified; the remaining items require
human action (submission, push, final review). This file mirrors
`PUSH_READY.md` §8 and adds the submission steps. As of 2026-08-09 all
automated gates (reproducibility, integrity, paper/proposal compile,
anonymity, secret scan, release branch + tag) are closed.

## Reproducibility and integrity

- [x] `make reproduce` green: statistics (primary + replication + combined),
      integrity (15/15), verification bundle (17/17, VERDICT PASS), independent
      stats crosscheck (PASS), figures, starter-kit leaderboard, paper PDF,
      proposal PDF
- [x] Freeze manifests intact (VER-1 ×6 PASS; VER-2: 12 + 5 + 8 bound inputs
      byte-identical; generated report exception documented — see
      `FINAL_AUDIT_REPORT.md` INC-1)
- [x] Paper compiles: 6 pages (≤ 8), 0 overfull, 0 undefined, 2 figures,
      references resolve
- [x] Proposal compiles: 3 pages (≤ 4), 0 overfull, 0 undefined
- [x] Starter kit: anti-gaming tests 9/9, ruff clean on `competition/`
- [x] Secret scan: tracked files clean (0 findings); exceptions are false
      positives (documented)

## Anonymity (paper)

- [x] Automated scan of build sources + PDF bytes: no company names, no repo
      paths, no person names, no API keys, no internal hostnames
- [x] Implementation named only PSBE-Runtime; model names are public
      (DeepSeek V4 Pro, Kimi K3) and required for reproducibility
- [ ] Human visual review of `paper/main.pdf` (final page-by-page pass)
- [x] Stale v3 tex snapshots purged from `paper/compiled/` and
      `paper/generated/`

## Honesty and claim discipline

- [x] P2 ≈ P3: no superiority claim anywhere in paper or competition docs
- [x] H4 marked NOT TESTABLE; no P1 claims
- [x] No TEE / formal-guarantee / training-data claims
- [x] v3 withdrawal and replication-n discrepancy documented
      (`RESEARCH_HISTORY.md`); replication cost gap documented
- [x] Findings report caveats (§9) reproduced in the paper's Limitations

## Release

- [x] `PUSH_READY.md` current (branch structure, commands, naming rules)
- [x] `FINAL_AUDIT_REPORT.md` written (incl. INC-1–3)
- [x] `SUBMISSION_METADATA.md` written
- [x] `EXECUTIVE_SUMMARY.md` written
- [x] `REPRODUCIBILITY.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `CITATION.cff`
      written
- [x] Release branch `release/finboundbench-icaif26` created, curated,
      committed, tagged `finboundbench-icaif26-v1.0` (commits `7b3e4ea`,
      `01d562b`)
- [x] Secret scan re-run immediately before push (2026-08-09: tracked files
      clean, allowlist enforced)

## Submission (human action, Aug 9 deadline)

- [ ] Register/confirm CMT access for ICAIF 2026 ("Competitions" option)
- [ ] Replace organizing-committee placeholder with real author block +
      contact email in the proposal
- [ ] Upload `competition/icaif26_finboundbench_proposal.pdf` to CMT before
      Aug 9 23:59 AOE
- [ ] Submit paper to main track before Aug 9 AoE (if pursuing main track;
      competition track does not preclude it — verify overlap policy on the
      ICAIF site)
- [ ] Watch acceptance notification window Aug 17–20
