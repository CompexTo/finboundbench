# V3 confirmatory raw stream audit

Recorded: 2026-08-06
Audited artifact: `results/v3/confirmatory-reduced/raw/events.jsonl`
sha256: `1a7b85c6d3b3b683376584b079be7830f0201b6bf6f474f63b87752faabdcd5d`
Related deviations: PD-V3-003 (`PROTOCOL_DEVIATIONS.md`)
Related audits: `TRANSMITTED_FIELD_AUDIT.md`, `METRIC_CORRECTION.md`

This audit was computed directly from the raw JSONL (330 lines) and the pair
files under `data/v2/generated/`. No derived artifact was trusted.

---

## 1. Planned vs actual

| Item | Planned (config + runner) | Actual in stream |
|---|---|---|
| Models | 1 admitted lane (`google/gemma-4-26b-a4b-it`; kimi-k3 and deepseek-v4-pro commented out of the config) | 1 model, 330/330 events |
| Conditions | 2 (`B0`, `P3`) | 2 (B0: 150, P3: 180) — **unequal** |
| Datasets | 2 (`hmda-2024-dc-v3`, `cfpb-complaints-2024-01-dc-v3`) | 2 (HMDA: 240, CFPB: 90) — **unequal** |
| Pairs per dataset | "40 pairs" per runner label | Pair files contain 40 variant rows = **20 pairs** each; HMDA ran 20 pairs × 2 conditions; CFPB ran 5 pairs in B0, 10 pairs in P3 |
| Repetitions | 3 | 3 (110 events per repetition) |
| Expected invocations | 480 (2 × 2 × 1 × 40 rows × 3) | 330 executed |
| Run manifest | `confirmatory-reduced/manifests/run-manifest.json` | **missing — the manifests directory is empty**; the runner's final manifest write never happened |

The runner iterated over pair-file **rows**, not pairs: each pair contributes
two variant rows (A and B), so every `(dataset, condition, pair_id,
repetition)` cell appears exactly **twice** (165 unique cells × 2 = 330).
Variant A and B transmitted byte-identical payloads (see
`TRANSMITTED_FIELD_AUDIT.md`), so these duplicates are not independent
observations of anything that varied.

## 2. Headline counts

| Count | Value |
|---|---|
| Total events | 330 |
| Completed with result | 329 |
| Provider failures | 1 (`RuntimeError: PROVIDER_TIMEOUT`, seq 48, B0, HMDA pair `hmda-f15566c4af885906f608`, rep 3) |
| Release-allowed | 263 |
| Release-denied | 66 |
| Distinct pair_ids | 30 |
| Event hash chain | intact (0 broken links, sequences 1-330 contiguous) |
| Committed budget | EUR 0.88075 (`raw/budget/reduced-ledger.jsonl`, 662 entries) |
| Sum of provider-attributed evidence cost | EUR 0.13076 |

## 3. Counts by model

| Model | Events |
|---|---|
| google/gemma-4-26b-a4b-it (lane google-gemma-4-26b-a4b-it) | 330 |

One model only. Kimi-k3 and DeepSeek-v4-pro remain commented out of the R2
config (rate-limit history preserved in admission records). **No multi-model
confirmation exists.**

## 4. Counts by dataset

| Dataset | Events | Pairs covered |
|---|---|---|
| hmda-2024-dc-v3 | 240 | 20 |
| cfpb-complaints-2024-01-dc-v3 | 90 | 10 (only 5 in B0) |

## 5. Counts by condition

| Condition | Events | Release-allowed | Release-denied | No result |
|---|---|---|---|---|
| B0 | 150 | 124 | 25 | 1 (timeout) |
| P3 | 180 | 139 | 41 | 0 |

## 6. Counts by dataset × condition

| Dataset | Condition | Events | Pair coverage |
|---|---|---|---|
| hmda-2024-dc-v3 | B0 | 120 | 20 pairs |
| hmda-2024-dc-v3 | P3 | 120 | 20 pairs |
| cfpb-complaints-2024-01-dc-v3 | B0 | 30 | 5 pairs |
| cfpb-complaints-2024-01-dc-v3 | P3 | 60 | 10 pairs |

## 7. Counts by pair and repetition

- 25 pairs × 12 events (HMDA 20 pairs + CFPB pairs covered by both B0 and P3)
- 5 pairs × 6 events (CFPB pairs covered by P3 only)
- Every cell `(dataset, condition, pair_id, repetition)` appears exactly twice
  (variant-row duplication).
- Repetition totals: rep 1 = 110, rep 2 = 110, rep 3 = 110.

## 8. Exact exclusion and failure reasons

| Reason | Count | Classification |
|---|---|---|
| `PROVIDER_TIMEOUT` (seq 48) | 1 | provider failure — failure record, not an experimental result |
| Release denial `Artifact is not valid JSON` | 330 denial events (one per completed execution's json-schema validator) | see note |
| Release denial `Artifact size N exceeds the 8192-byte release limit` | 66 | the 66 finally-denied releases |
| Release denial reason codes on finally-denied artifacts | json-schema DENY + required-fields DENY + decision-vocabulary DENY + numeric-bounds DENY + max-bytes DENY + prohibited-field-names DENY | all driven by truncated outputs |

Note on the 330 "not valid JSON" denial events: every completed execution's
validator chain recorded a `compex.output.json-schema DENY` event, yet 263
executions ended with `nativeRelease.allowed = true` because later validators
emitted ALLOW verdicts (e.g. "No prohibited exact value was found in the
non-JSON artifact") and the chain's final decision allowed release. This
means the release policy as configured does not fail closed on a DENY from a
validator listed in `requiredValidators`. This behavior is itself a release
boundary defect to investigate before any further live run (tracked in the
transmitted-field audit's blocking findings).

The 66 denied artifacts all had `outputTokens = 2048` (the configured cap):
the model emitted repetitive ~62 KB non-JSON continuations. The model was
asked to route a record while receiving only an opaque record-id hash as
input (see `TRANSMITTED_FIELD_AUDIT.md`), which explains the degenerate
outputs.

## 9. Timing anomalies

Inter-call spacing is normally the configured 2 s sleep plus call latency.
Gaps of ~2.8-2.9 minutes appear between seq 150→151 (B0-CFPB → P3-HMDA) and
seq 270→271 (P3-HMDA → P3-CFPB), consistent with operator pauses or restarts
between phases.

## 10. Unreconstructable anomaly: CFPB B0 truncation

B0 executed only the first **10 rows** (5 pairs) of the CFPB pair file while
P3 executed the first **20 rows** (10 pairs). Both phases iterate the same
in-memory pair list in the checked-in runner, so this asymmetry cannot be
reproduced from current code, and the missing run manifest means the exact
execution context cannot be reconstructed from preserved artifacts.
Classification: **protocol execution anomaly; the affected events are audit
records only and must not enter any analysis.**

## 11. Verdict

The stream is a valid append-only record of 330 live OpenRouter invocations
and is usable **only** as:

> A live execution and release-policy diagnostic over one commercial model
> lane.

It is **not** usable for:

- AUR (no task utility, no ground truth scoring, identical payloads across conditions),
- UIR (zero counterfactual contrast: pair members transmitted byte-identical payloads),
- any multi-model, multi-condition or purpose-selectivity claim.

Blocking prerequisites before any continuation: fixes and tests in
`TRANSMITTED_FIELD_AUDIT.md`, a written run manifest, equal condition and
dataset coverage, and the one-pair live B0/P3 validation gate.
