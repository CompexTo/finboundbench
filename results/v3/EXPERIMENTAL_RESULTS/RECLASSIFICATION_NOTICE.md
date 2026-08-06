# RECLASSIFICATION NOTICE — 2026-08-06

The files in this folder are preserved unchanged for audit history, but the
characterization in `README.txt` is overridden by
`results/v3/manifests/v3-instrumentation-freeze.json`
(scope `INSTRUMENTATION_AND_REDUCED_LIVE_EXECUTION_ONLY`) and by protocol
deviations PD-V3-002 / PD-V3-003 in `docs/v3/PROTOCOL_DEVIATIONS.md`.

Specifically:

- `v3-final-freeze.json` is NOT a final experimental freeze.
- The metrics listed under "KEY METRICS" in `README.txt` are INVALID or
  TEST-DOUBLE values and must not be cited (see
  `docs/v3/METRIC_CORRECTION.md`):
  - AUR 0.9341 — invalid formula (pass-rate ratio, not utility retention)
  - UIR 0.2000 — invalid formula (release-denial rate, not influence rate)
  - SPCR 0.2426, EVC 1.0000, Availability 0.9857, Overhead 1.3116x —
    deterministic test-double outputs, not experiments
- `confirmatory-reduced-events.jsonl` transmitted only `source_record_id` in
  every invocation (see `docs/v3/TRANSMITTED_FIELD_AUDIT.md`) and is a live
  execution and release-policy diagnostic over one commercial model lane, not
  a confirmatory study.

Primary research claims are not permitted from this package. The paper is
not submission-ready. Do not submit.
