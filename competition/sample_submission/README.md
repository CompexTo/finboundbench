# FinBoundBench sample submission (Track A)

A deliberately simple, fully deterministic Track A submission that needs no
API key and no network. It demonstrates the submission contract:

- authorized + governed (`A3`): the confidential value may influence the action
- prohibited + governed (`P3`): a public-only rule is used; the confidential
  value never influences the decision
- ungoverned lanes (`A1`, `P0`): the field is used when present, mirroring an
  ungoverned reference system
- stripped lanes (`A0`, `P2`): public-only rule

The public rule is a placeholder hash heuristic; a competitive submission
replaces it with an ML or LLM policy over `public_fields`.

## Files

- `decide.py` — the submission entrypoint (`decide(payload) -> dict`)
- `submission.json` — submission metadata per `submission_schema.json`

## Score it

```bash
python -m competition.evaluator.run_baselines --submission competition/sample_submission/decide.py
```

Expected signature: constraint pass (NetUI = 0, zero violations, availability
1.0) with moderate authorized utility (AUR above 0 but below the 0.80 gate —
the sample intentionally does not win; it demonstrates a *valid* submission).
