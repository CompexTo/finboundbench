# Executive Summary — FinBoundBench ICAIF 2026 package

Status: FINAL (2026-08-09). Concise summary of what was delivered, what was
found, and what remains human.

## What we built

A complete, self-contained research package for the ICAIF 2026 competition
track and main track:

1. **FinBoundBench** — a paired benchmark measuring purpose-selective AI on
   financial decision systems: the same consumer-finance case rendered into
   purpose-labeled counterfactual variants (authorized / prohibited / masked),
   with the model's own nondeterminism as a decision floor.
2. **PSBE** — Purpose-Selective Bounded Execution, the measured decision-level
   property: prohibited influence at/below the floor, authorized utility
   retained.
3. **PSBE-Runtime** — a governed execution adapter (purpose contract,
   projection, output validation, hash-linked evidence chain, no fallback)
   implementing the governed conditions.
4. **Confirmatory evidence** — preregistered, frozen, independently re-computed
   across two model families and two financial tasks.
5. **Competition package** — 4-page proposal (3 pp) + complete starter kit
   (harness, 7 degenerate baselines + oracle, sample submission, schema,
   rules, container spec) with a validated, non-gameable leaderboard.
6. **Paper** — anonymous 8-page-limit paper (6 pp, 2 figures, clean build).
7. **Release** — curated `release/finboundbench-icaif26` branch plan
   (`PUSH_READY.md`) with `make reproduce` green.

## What the evidence shows

- **The failure mode is real and strong**: prohibited-visible data changed
  decisions on 96–100% of cases (primary UIR 1.00; replication 0.9646) versus
  a natural-decision floor of 0.00–0.0375.
- **Masking works**: deterministic and governed masking suppressed influence
  to at or below the floor in every condition of both studies.
- **Purpose helps authorized utility**: declaring purpose raised balanced
  accuracy 0.32→0.71 (primary, gain +0.39, p=0.0002) and 0.625→0.733
  (replication, gain +0.108, p=0.002).
- **Governance is free**: governed execution retained the full authorized gain
  (AUR = 1.0 in both studies) — purpose selectivity does not cost utility.
- **No superiority claim**: governed masking and deterministic masking were
  statistically equivalent (P2 ≈ P3); the contribution is the joint property
  and its measurement, not a runtime race.

## Honest caveats (as documented)

- Two (model, task) pairs only; H4 not testable; no TEE/formal guarantees;
  provider drift observed (7 windows for the replication); replication cost
  not frozen; registered replication n (500) vs executed (120) documented.

## What remains human (blocked here)

1. CMT submission of the proposal (deadline Aug 9, 23:59 AOE) with the real
   author block — placeholder is "The FinBoundBench Organizing Committee".
2. Main-track paper submission (Aug 9 AoE extended) after final human review.
3. `git push` of the release branch — no remote/`gh` on this machine; exact
   commands in `PUSH_READY.md` §7.
4. Human review areas per findings report §9 (purpose policies, condition
   equivalence, metrics, statistical plan, model selection, exclusions,
   interpretation).

## One-line pitch

A financial institution may hold a field lawfully and still have it quietly
flip prohibited decisions; FinBoundBench measures and bounds that influence
against the model's own noise, and shows a governed adapter can be
purpose-selective without losing authorized utility.
