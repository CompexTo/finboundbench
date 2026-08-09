# Secret Scan Exceptions

Companion to `SECRET_SCAN_REPORT.md` (generated 2026-08-09 by
`scripts/scan_secrets.py`). Each working-tree finding is classified here.
None is a live credential; the tracked release set is clean.

The table below doubles as the scan's allowlist: `scan_secrets.py` reads it,
and a documented (file, pattern) pair does not fail the "tracked files clean"
gate. Any new release file with credential-shaped strings must be reviewed and
added to the table (with a classification) before the scan can pass.

| File | Pattern | Classification |
|---|---|---|
| `src/purposebench/v4/eligibility_runner.py` | auth_basic | False positive: the identifier `confidential_token` (the `SYNTHETIC_*` value "HIGH"/"LOW" passed to the oracle label function), the config key `outputTokenLimit: 512` (model output token cap), and the env-var *name* `OPENROUTER_API_KEY` in a provider-error handler (the value is never present; the key is read from the environment only at runtime). |

## Standing rules

- `.env` (contains `COMPEX_API_KEY`, `MODEL_API_KEY`) is gitignored and
  untracked; it must never be added to any branch.
- Any file that must be added to the release branch with credential-shaped
  strings must first be reviewed and this document updated.
- The scan is re-runnable: `python scripts/scan_secrets.py` (exits with a
  warning if undocumented tracked findings remain; documented exceptions
  pass).
