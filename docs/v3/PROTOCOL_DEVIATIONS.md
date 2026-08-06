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

## Deviation PD-V3-002 — final-freeze manifest mislabelled an instrumentation package

- Recorded: 2026-08-06
- Stage: freeze classification
- Affected manifest: `results/v3/manifests/v3-final-freeze.json`
  (sha256 `72d414c5c11f8376a2f8a80c6450451a7f1807e738fad3c20f1987dd9875c9c9`)
- Failure: the manifest is labelled "Final experimental freeze with all
  artifacts", reports six primary metrics as frozen results, and lists
  "Paper submitted to venue" as a next step. In reality only the reduced
  Gemma OpenRouter lane used live provider execution; the attack, DP,
  evidence-verification, availability and overhead streams are deterministic
  test doubles, and the statistical report's AUR/UIR formulas do not
  implement the preregistered definitions.
- External effects: none; no submission occurred.
- Correction: manifest preserved unchanged for audit history; reclassified by
  `results/v3/manifests/v3-instrumentation-freeze.json` with scope
  `INSTRUMENTATION_AND_REDUCED_LIVE_EXECUTION_ONLY`. Primary research claims
  are not permitted from this package. See `docs/v3/METRIC_CORRECTION.md`.

## Deviation PD-V3-003 — confirmatory stream transmitted only `source_record_id`

- Recorded: 2026-08-06
- Stage: R2 reduced confirmatory execution
- Affected artifacts: `results/v3/confirmatory-reduced/raw/events.jsonl`
  (sha256 `1a7b85c6d3b3b683376584b079be7830f0201b6bf6f474f63b87752faabdcd5d`,
  330 events)
- Failure: the R2 confirmatory config pinned
  `selected_fields: [source_record_id]`, so the projection sent to the model
  contained no public financial fields and no confidential fields. B0 and P3
  transmitted byte-identical projections; the `purpose_binding` condition flag
  never influenced the payload. Additionally, 66/329 completed executions were
  release-denied because outputs were truncated non-JSON artifacts
  (outputTokens = 2048 cap), and CFPB B0 covered only 5 of the 10 pairs used
  by CFPB P3.
- External effects: ~EUR 0.88 committed on the reduced lane (budget ledger
  `results/v3/confirmatory-reduced/raw/budget/reduced-ledger.jsonl`).
- Correction: stream preserved unchanged; audited in
  `docs/v3/CONFIRMATORY_RAW_AUDIT.md` and `docs/v3/TRANSMITTED_FIELD_AUDIT.md`.
  The confirmatory experiment must not continue until the transmitted-field
  defect is fixed and re-validated with a live one-pair B0/P3 gate.
