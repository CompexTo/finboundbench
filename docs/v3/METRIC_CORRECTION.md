# V3 metric correction

Recorded: 2026-08-06
Status: REQUIRED BEFORE ANY PRIMARY CLAIM
Related deviation: PD-V3-002 (`PROTOCOL_DEVIATIONS.md`)
Affected derived artifact: `results/v3/statistical-analysis/derived/statistical-report.json`
Produced by: `scripts/run_v3_statistical_analysis.py`

The statistical report labelled every metric `INSTRUMENTATION_ONLY`, but the
v3 final-freeze manifest and downstream paper assets still circulated six
numeric values as if they were experimental results. None of the six values
measures what its name claims. This document records each invalid
calculation, the correct definition, and the replacement required before any
primary claim may be made.

---

## 1. AUR — Authorized Utility Retention

### Previous invalid calculation

```python
b0_pass_rate = PASSED(B0) / total(B0)
p3_pass_rate = PASSED(P3) / total(P3)
AUR = p3_pass_rate / b0_pass_rate          # reported value: 0.9341
```

(`scripts/run_v3_statistical_analysis.py`, lines 65-80)

### Why the previous value cannot be used

- `PASSED` here means "native release allowed", i.e. an execution/release
  outcome. Execution success or release success is **not task utility**.
- The ratio compares release pass rates of two conditions that, in the live
  reduced stream, transmitted byte-identical payloads (`source_record_id`
  only), so even as a pass-rate ratio it measures nothing about governance.
- No task metric (accuracy, ROC-AUC, PR-AUC, F1, calibration, or structured
  decision correctness) was ever computed on any ground truth.

### Correct definition

```text
AUR =
(
Utility_PSBE_authorized
− Utility_public_only
)
/
(
Utility_full_authorized
− Utility_public_only
)
```

`Utility` must be a task metric measured against ground-truth labels:
accuracy, ROC-AUC, PR-AUC, F1, calibration, or correct structured decision
rate. All three component utilities (`Utility_PSBE_authorized`,
`Utility_public_only`, `Utility_full_authorized`) must be reported alongside
AUR. AUR must not be reported when the denominator
(`Utility_full_authorized − Utility_public_only`) is negligible or unstable;
report the denominator and its confidence interval first.

### Required raw fields

- Per-record ground-truth label for the authorized task (dataset task
  definition).
- Per-record structured model decision and/or score, parsed from released
  output only.
- Condition identifier for at least: `public_fields_only`,
  `full_data_authorized`, `psbe_authorized_confidential_use`.
- Pair/record identity, repetition, model, dataset, prompt hash, payload
  hash.

### Required analysis

- Task utility per condition with clustered bootstrap confidence intervals.
- Denominator stability check before division.
- Complete-case and conservative failed-closed variants.

### Replacement artifact

`results/v3/live/statistics/aur.json` (to be produced from
`results/v3/live/purpose-selective/` raw events; does not exist yet).

---

## 2. UIR — Unauthorized Influence Rate

### Previous invalid calculation

```python
uir = release_denied / total_events        # reported value: 0.2000
```

### Why the previous value cannot be used

This is a **release-denial rate**, not unauthorized influence. A release
denial is a policy outcome at the output boundary; it says nothing about
whether a prohibited confidential field changed the model's decision.
In the reduced live stream the 66 denials were caused by truncated non-JSON
outputs (model hit the 2048 output-token cap), not by prohibited-field
influence.

### Correct definition

```text
UIR =
counterfactual pairs whose governed decision or score changes
/
valid counterfactual pairs
```

A valid counterfactual pair requires, within each pair:

- all purpose-approved fields byte-identical between the two members;
- only predeclared prohibited confidential fields may differ;
- ground truth unchanged between members;
- both pair members complete successfully (release-allowed, schema-valid);
- pair mapping verified outside model-visible content;
- position and repetition effects separated (pair order varied, repetitions
  preregistered).

Changed responses must be classified before counting: unauthorized influence
vs execution nondeterminism vs position effect vs mapping failure vs provider
failure. Not every changed response is unauthorized influence.

### Required raw fields

- Pair identity with verified member mapping (A/B variants).
- Approved-field payload hash (must be identical within pair).
- Prohibited-field payload hash (must differ within pair).
- Structured decision and score per member, per repetition.
- Position/order indicator, repetition index.

### Required analysis

- Pairwise McNemar-style test on decisions; score-difference tolerance
  preregistered.
- Separation of influence from nondeterminism using same-member repetitions.
- UIS = 1 − UIR_bounded / UIR_unbounded reported with absolute UIR and
  confidence intervals.

### Replacement artifact

`results/v3/live/statistics/uih.json` (to be produced from
`results/v3/live/purpose-selective/`; does not exist yet).

---

## 3. SPCR — Silent Policy Compromise Rate

### Previous invalid calculation

Computed from `results/v3/attack-suite/raw/events.jsonl`, a deterministic
test-double oracle: `silent_compromise / attack_total = 57 / 235 = 0.2426`.

### Why the previous value cannot be used

No attack was executed against a real implementation. The outcomes are
predetermined oracle values. SPCR is the primary systems-security metric and
may only be reported after live attacks against all three architectures:

- A0 — conventional application baseline
- A1 — hardened application baseline
- A2 — PSBE-Runtime

Each attack must produce the actual request, actual runtime behavior,
prevention status, detection status, evidence, reproduction command, and
wall-clock timing.

### Correct definition

```text
SPCR =
successful boundary violations without reliable detection
/
valid boundary attacks attempted
```

### Replacement artifact

`results/v3/live/attacks/` + `results/v3/live/statistics/spcr.json`
(do not exist yet).

---

## 4. EVC — Evidence Verification Coverage

### Previous invalid calculation

Computed from the test-double evidence-verification stream:
`20 / 20 = 1.0000`.

### Why the previous value cannot be used

No real evidence bundles were produced from live PSBE executions, and no
independent verifier (automated or blinded human) checked them. EVC may only
be reported after real evidence bundles exist and are verified against the
full control checklist (purpose, approval, dataset identity and version,
projection, workload, model, route, prompt hash, network policy, tool policy,
privacy policy, output release, expiry, revocation, artifact hashes).

### Correct definition

```text
EVC =
independently verified required controls
/
required controls
```

### Replacement artifact

`results/v3/live/evidence/` + `results/v3/live/statistics/evc.json`
(do not exist yet).

---

## 5. Availability

### Previous invalid calculation

Computed from the test-double availability stream: `345 / 350 = 0.9857`.

### Why the previous value cannot be used

The stream contains generated outcomes, not measured executions. Availability
must be measured as policy-preserving completion over actual wall-clock
executions of every architecture under test, on the same hardware, model,
payload and repetition scheme, with failures preserved.

### Correct definition

Policy-preserving completion rate (PPCR) and provider-compatibility rates
computed from measured executions; failures classified, not dropped.

### Replacement artifact

`results/v3/live/availability/` (does not exist yet).

---

## 6. Overhead

### Previous invalid calculation

```python
overhead = mean(P3 executionTimeMs) / mean(B2 executionTimeMs)  # 1292.98 / 985.78 = 1.3116
```

where `executionTimeMs` values were generated by the test-double producer.

### Why the previous value cannot be used

The timings are fabricated, not measured. Overhead may only be reported from
measured wall-clock executions with warmup excluded under a predeclared rule,
reporting median and p95 (not only means), failure rate and monetary cost,
same hardware/model/payload/repetitions across:

- conventional baseline
- hardened baseline
- PSBE projection
- PSBE projection plus release
- PSBE with evidence

### Replacement artifact

`results/v3/live/availability/` + `results/v3/live/statistics/overhead.json`
(do not exist yet).

---

## Disposition of previous values

| Metric | Old value | Status | Permitted use |
|---|---|---|---|
| AUR | 0.9341 | INVALID | none; must not appear in any paper, slide, or marketing asset |
| UIR | 0.2000 | INVALID | none |
| SPCR | 0.2426 | TEST DOUBLE | instrumentation only, never as a result |
| EVC | 1.0000 | TEST DOUBLE | instrumentation only, never as a result |
| availability | 0.9857 | TEST DOUBLE | instrumentation only, never as a result |
| overhead | 1.3116 | TEST DOUBLE | instrumentation only, never as a result |

The old statistical report remains on disk unchanged for audit history. The
replacement analysis pipeline must write only under `results/v3/live/` and
must fail closed if any required raw field is missing.
