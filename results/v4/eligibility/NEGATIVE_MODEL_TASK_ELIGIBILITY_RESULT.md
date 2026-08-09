# Negative Model/Task Eligibility Result — Protocol V4 (frozen pointer)

**This is a frozen copy/pointer. It must not be reinterpreted here.** The
canonical frozen negative evidence record is:

`docs/v4/NEGATIVE_MODEL_TASK_ELIGIBILITY_RESULT.md`

The underlying v3 artifacts are **preserved at `results/v3/`** and must never
be deleted or altered:

- `results/v3/matrix-rebuild/analysis/matrix-analysis.json` (Task A)
- `results/v3/matrix-rebuild/taskB/analysis/matrix-analysis.json` (Task B)

## Frozen facts (numbers only — no interpretation here)

- 3360 real inferences (1680/task), live Gemma matrix,
  `OPENROUTER_PURPOSE_SELECTIVE_MATRIX_REBUILD_NOT_CONFIRMATORY`,
  `confirmatoryClaimsPermitted: false`.
- Task A: baseline (public-only) BACC 0.4942; full oracle 0.6559
  (authorized gain +0.1617); PSBE AUR ≈ −0.58 … −0.91 across P0–P3.
- Task B: sensitivity gate failed (oracle < baseline).
- Prohibited full-record influence (B0 UIR 0.0, B1 0.069) at/below the
  identical-input nondeterminism floor (0.09–0.16).

## Rule encoded

A model/task configuration must pass signal/influence/stability gates
(Gates A–D) before a confirmatory benchmark is run — see
`docs/v4/ELIGIBILITY_GATES.md` and `src/purposebench/v4/gates.py`.