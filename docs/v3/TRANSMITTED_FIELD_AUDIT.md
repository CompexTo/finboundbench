# V3 transmitted-field audit

Recorded: 2026-08-06
Audited artifact: `results/v3/confirmatory-reduced/raw/events.jsonl`
(330 events; sha256 `1a7b85c6d3b3b683376584b079be7830f0201b6bf6f474f63b87752faabdcd5d`)
Status: **BLOCKING — the confirmatory experiment must not continue until section 5 is resolved and section 6 tests pass.**

Every one of the 329 completed events records exactly:

```json
"transmittedFields": ["source_record_id"]
```

(329 events with that singleton list; 1 timeout event with no evidence.)

---

## 1. Question posed

Which of the following explains the observation?

1. Only `source_record_id` was actually transmitted.
2. Financial fields were inside an unrecorded nested payload.
3. Evidence generation omitted nested fields.
4. The research request builder incorrectly projected the record.
5. The field-enumeration code is incomplete.

## 2. Method

Traced the full data path:

1. Pair files `data/v2/generated/{hmda,cfpb}-*-pairs.jsonl` — 22/17 approved
   fields per pair plus 6 prohibited synthetic confidential fields; variant A
   and B rows differ **only** in the 6 prohibited fields; `source_record_id`
   is identical across variants (verified directly).
2. Runner `scripts/run_v3_confirmatory_reduced.py` (lines 234-241) projects
   each record as `fields ∩ selected_fields ∩ approved_fields`, where
   `selected_fields` comes from
   `configs/v3/openrouter-confirmatory-matrix-v3.yaml`.
3. Config sets `selected_fields: [source_record_id]` — a singleton.
4. Bridge `scripts/governed_openrouter_bridge_v3.cjs` forwards
   `selectedFields` unchanged to the platform adapter.
5. Platform adapter `services/runner/src/providers/commercial-model-adapter.ts`
   (validateInvocation) **enforces** that every record's key set equals
   `selectedFields` exactly, then transmits
   `projectionText = canonicalJson({selectedFields, records})` and records
   `evidence.transmittedFields = [...selectedFields]`.

Because step 5 hard-validates record keys against the declared manifest,
hypotheses 2, 3 and 5 are excluded: no unrecorded nested payload could pass
validation, evidence generation mirrors the validated manifest, and the
enumeration is complete with respect to what was validated.

## 3. Finding

**Hypotheses 1 and 4 are both true and are the same defect.**

- Only `source_record_id` was actually transmitted (hypothesis 1). The
  evidence is faithful: `requestBytes` of 1376-1433 bytes is consistent with
  prompts plus a single hash-valued field, and the adapter's key-equality
  check makes any larger payload impossible.
- The cause is the research request builder and its config (hypothesis 4):
  the R2 config pinned `selected_fields` to `[source_record_id]`, so the
  projection dropped every public financial field (income, loan_amount,
  interest_rate, complaint narrative fields, ...) and every confidential
  field before transmission.

## 4. Consequences for the live stream

1. **No task-relevant data reached the model.** The routing prompt asks for
   a decision based on risk band and queue age, but no such fields were in
   the payload. This is the direct cause of the degenerate outputs (66
   truncated 2048-token non-JSON continuations → release denial).
2. **Zero counterfactual contrast.** Pair members A/B differ only in
   prohibited fields; the projection transmitted only `source_record_id`,
   which is identical across variants. Verified in raw events: 54 of 55
   `(pair, condition)` groups have a single `payloadHash`; the 55th is the
   timeout pair. UIR is uncomputable from this stream.
3. **Zero condition contrast.** B0 (`full_data_no_purpose_policy`) and P3
   (`psbe_full_evidence`) used the identical projection code path and
   identical config. The condition's `purpose_binding` flag is consumed by
   nothing in the runner: it only enters the contract hash. Whatever
   differences exist between B0 and P3 outcomes are model nondeterminism,
   not governance.
4. **No purpose-selective claim is possible from this stream.** It is a live
   execution and release-policy diagnostic over one commercial model lane —
   nothing more.

## 5. Required resolution (blocking)

1. Replace the singleton `selected_fields` mechanism with a per-condition
   projection spec:
   - Authorized conditions transmit the purpose-approved projection
     (all approved public fields; confidential fields only where the
     condition's purpose approves them).
   - `full_data_*` conditions additionally transmit the prohibited fields.
   - Prohibited-purpose conditions vary only prohibited fields within pairs.
2. Make the condition identity causally effective: the projection,
   contract, and release policy must differ between conditions by design,
   and the difference must be recorded in evidence.
3. Require the evidence schema to distinguish approved vs prohibited
   transmitted fields (platform change, see section 6).
4. Fix the release-policy fail-closed behavior: 263 executions were released
   despite a DENY from `compex.output.json-schema`, which the run config
   listed in `requiredValidators` (see `CONFIRMATORY_RAW_AUDIT.md` §8).
5. Re-validate with a live one-pair B0/P3 gate before any matrix run:
   verify exact payload and field differences between pair members and
   between conditions from evidence, not from config intent.

## 6. Required tests (must fail until the defect is fixed)

Platform (Compex repo, `services/runner`):

- evidence lists all transmitted fields, partitioned into approved and
  prohibited sets, when a projection classification is supplied (B0 case:
  permitted + prohibited fields both listed);
- evidence lists exactly the purpose-approved projection with an empty
  prohibited set for approved-only executions (P3 case);
- `payloadHash` changes when the permitted payload changes;
- pair members with identical approved fields produce identical
  approved-payload hashes;
- pair members differing only in declared prohibited fields produce equal
  approved-payload hashes and different prohibited-payload hashes.

Research repo (`tests/v3/test_transmitted_field_audit.py`):

- the same five invariants asserted against the pair builder and payload
  construction used by the runner;
- a regression test that the confirmatory config's `selected_fields` can
  never again exclude approved task fields from an authorized condition.

## 7. Disposition

- The 330-event stream is preserved unchanged.
- No derived metric may consume it for purpose-selectivity claims.
- The freeze reclassification (`results/v3/manifests/v3-instrumentation-freeze.json`)
  records this limitation.
