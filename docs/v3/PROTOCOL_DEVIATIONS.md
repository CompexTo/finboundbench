# Protocol v3 deviations and failed gates

## Freeze attempt 1 — invalid before execution

- Stage: dry-run freeze verification
- Original manifest commit: `43455f7895e2156fda1bfd08c9d76cd788e5d703`
- Original manifest self-hash:
  `40144d2d0e0ca749c3ce26d80684de05aa50e3674f0c007898a2256d7242638a`
- Failure: the new verifier's Git-ancestor helper accepted only 64-character
  identifiers, while these repositories use 40-character SHA-1 commits.
- Outcome visibility: none; the retained official dry run had not started.
- External effects: zero provider calls, zero paid cost, zero AWS actions.
- Correction: accept either 40- or 64-character lowercase Git object IDs, add
  regression coverage, commit the corrected code, and build a new freeze
  manifest. Do not reuse the failed manifest.

The exact failed manifest remains in Git commit `43455f7`; the current tree also
contains `protocol-v3-psbe-no-tee-dry-run-freeze-attempt-1-invalid.json` so the
failure is visible without history archaeology.
