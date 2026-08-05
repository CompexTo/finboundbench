# OpenRouter R0/R1/R2 Experimental Results — Decision Record

**Date**: 2026-08-05
**Author**: PSBE Research
**Status**: COMPLETE

## Summary

Ran R0 admission, R1 position diagnostic, and R2 confirmatory matrix on 5 OpenRouter models. 3 models admitted, 15/18 R1 positions passed, 32/36 R2 confirmations passed.

## R0 Admission (Schema + Route + Cost Gate)

| Model | Status | Route | Manifest Hash |
|-------|--------|-------|---------------|
| moonshotai/kimi-k3 | ✅ ADMITTED | morph | a2103169... |
| google/gemma-4-26b-a4b-it | ✅ ADMITTED | siliconflow/fp8 | f51178cd... |
| deepseek/deepseek-v4-pro | ✅ ADMITTED | coreweave/fp8 | 8d19c57b... |
| openai/gpt-5.6-luna | ❌ ROUTE_DRIFT | — | — |
| meta-llama/llama-4-maverick | ❌ ROUTE_DRIFT | — | — |

**Decision**: Admit 3 models. Reject 2 due to unstable route assignment (route changes between captures).

## R1 Position Diagnostic

18 invocations (6 layouts × 3 models):

| Model | PASSED | RELEASE_DENIED |
|-------|--------|----------------|
| moonshotai/kimi-k3 | 6/6 | 0 |
| google/gemma-4-26b-a4b-it | 3/6 | 3 |
| deepseek/deepseek-v4-pro | 6/6 | 0 |

**Decision**: All 3 models pass position diagnostic. gemma-4-26b has layout-sensitive release denials (3/6 layouts denied).

## R2 Confirmatory Matrix

36 invocations (2 datasets × 2 conditions × 3 reps × 3 models):

| Model | PASSED | RELEASE_DENIED |
|-------|--------|----------------|
| moonshotai/kimi-k3 | 12/12 | 0 |
| google/gemma-4-26b-a4b-it | 8/12 | 4 |
| deepseek/deepseek-v4-pro | 12/12 | 0 |

**Decision**: kimi-k3 and deepseek-v4-pro are fully confirmatory. gemma-4-26b has 33% release denial rate on CFPB dataset.

### R2 Disaggregated (from raw events)

By model × dataset:

| Model | HMDA | CFPB | Total |
|-------|------|------|-------|
| deepseek-v4-pro | 6/6 | 6/6 | 12/12 |
| kimi-k3 | 6/6 | 6/6 | 12/12 |
| gemma-4-26b | 6/6 | 2/6 | 8/12 |
| **Total** | **18/18** | **14/18** | **32/36** |

By model × condition:

| Model | B0 | P3 | Total |
|-------|----|----|-------|
| deepseek-v4-pro | 6/6 | 6/6 | 12/12 |
| kimi-k3 | 6/6 | 6/6 | 12/12 |
| gemma-4-26b | 4/6 | 4/6 | 8/12 |
| **Total** | **16/18** | **16/18** | **32/36** |

Full cross-tab (model × dataset × condition, 3 reps each):

| Cell | PASSED | RELEASE_DENIED |
|------|--------|----------------|
| deepseek × HMDA × B0 | 3/3 | 0 |
| deepseek × HMDA × P3 | 3/3 | 0 |
| deepseek × CFPB × B0 | 3/3 | 0 |
| deepseek × CFPB × P3 | 3/3 | 0 |
| kimi × HMDA × B0 | 3/3 | 0 |
| kimi × HMDA × P3 | 3/3 | 0 |
| kimi × CFPB × B0 | 3/3 | 0 |
| kimi × CFPB × P3 | 3/3 | 0 |
| gemma × HMDA × B0 | 3/3 | 0 |
| gemma × HMDA × P3 | 3/3 | 0 |
| gemma × CFPB × B0 | 1/3 | 2 |
| gemma × CFPB × P3 | 1/3 | 2 |

## Budget

| Phase | Committed EUR |
|-------|--------------|
| R0 + R1 | 30.44 |
| R2 | 23.33 |
| **Total** | **53.77** |

## Bugs Fixed

1. **Manifest hash mismatch**: Python `sha256_json` serialized `routeUptimeLast5m` as `100.0` (float) while Node.js `hashCanonicalJson` serialized as `100` (integer). Fixed by checking `.is_integer()` and converting to `int`.
2. **Record format**: Records must contain all `selectedFields` as keys in a single dict, not one dict per field.
3. **R1 budget cap**: Hardcoded `absolute_authorized_eur=2.0` in position diagnostic script; shared ledger had €29+ committed. Fixed to read from config.
4. **R1 selected_fields**: Config had fields not present in pilot data. Updated to match pilot data fields.

## Provenance Audit (2026-08-05)

Full audit at `docs/v3/V3_PROVENANCE_AUDIT.md`. Freeze manifest at `results/v3/manifests/v3-diagnostic-freeze.json`.

**Key findings**:
- v2 freeze intact with expected commits and manifest hash
- R1 raw events verified (18 records, 15/18 PASSED)
- R2 raw events verified (36 records, 32/36 PASSED)
- R0 admission raw events **MISSING** (budget ledger confirms 5 reservations but raw events.jsonl not found)
- R2 condition/dataset table in earlier manuscript was incorrectly computed (10/12 figure was partial view)
- All manifest hashes now match between Python and Node.js
