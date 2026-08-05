# V3 Provenance Audit

**Date**: 2026-08-05  
**Audit scope**: v3 OpenRouter diagnostic run raw evidence  
**Audited by**: automated recompute (scripts/recompute_tables.py)

## v2 Freeze Verification

| Check | Result |
|-------|--------|
| Platform commit | `29e4b2ea96f75263dc8fea82c41b4273be7ad7f3` (v2 freeze) |
| Research commit | `b4fac30cf1663be082b9e052496650be953cc91f` (v2 freeze) |
| Manifest hash | `923d9c26eb20309ad05fc4cf9628ad6c6c0b1ab1fe19a2a5b997a9b75bca1afe` |
| Manifest exists | `results/v2/manifests/protocol-v2-local-freeze.json` |
| Evidence audit exists | `results/v2/derived/protocol-v2-local-evidence-audit.json` |
| Status | **INTACT** — no source changes since freeze |

## v3 Raw Evidence Inventory

### R0 Admission (Route Verification)

| Artifact | Path | Status |
|----------|------|--------|
| Config | `configs/v3/openrouter-model-admission-v3.yaml` | Present |
| Freeze manifest | `results/v3/manifests/openrouter-admission-v3-freeze.json` | Present |
| Run manifest | `results/v3/openrouter-admission/manifests/run-manifest.json` | Present |
| Raw events | `results/v3/openrouter-admission/raw/events.jsonl` | **MISSING** |
| Budget ledger | `results/v3/raw/budget/openrouter-v3-ledger.jsonl` | Present (188 reservations, 188 settlements) |

**R0 claim (3/5 admitted)**: Cannot be verified from raw event evidence. Admission was verified in-session via live API calls. Raw events were either never written or were deleted during debugging. Budget ledger confirms 5 reservation+settlement pairs for R0 (subset of 188 total in combined R0/R1 ledger).

### R1 Position Diagnostic

| Artifact | Path | Status |
|----------|------|--------|
| Config | `configs/v3/openrouter-model-admission-v3.yaml` | Present |
| Raw events | `results/v3/position-diagnostic/raw/events.jsonl` | Present (181,109 bytes, 18 records) |
| Budget ledger | `results/v3/raw/budget/openrouter-v3-ledger.jsonl` | Present |

**Verified from raw**:
- Total: 15/18 PASSED, 3 RELEASE_DENIED, 0 FAILED
- By model: deepseek-v4-pro 6/6, kimi-k3 6/6, gemma-4-26b 3/6 (3 RELEASE_DENIED)
- By layout: all layouts have at least 2/3 PASSED
- Consistency: model_pass_sum(15) == r1_passed(15) ✓

### R2 Confirmatory Matrix

| Artifact | Path | Status |
|----------|------|--------|
| Config | `configs/v3/openrouter-confirmatory-matrix-v3.yaml` | Present |
| Raw events | `results/v3/confirmatory-matrix/raw/events.jsonl` | Present (540,418 bytes, 36 records) |
| Budget ledger | `results/v3/raw/budget/openrouter-v3-r2-ledger.jsonl` | Present (138 reservations, 138 settlements) |

**Verified from raw**:
- Total: 32/36 PASSED, 4 RELEASE_DENIED, 0 FAILED
- By model: deepseek-v4-pro 12/12, kimi-k3 12/12, gemma-4-26b 8/12
- By dataset: hmda-2024-dc-v3 15/18, cfpb-complaints-2024-01-dc-v3 17/18
- By condition: B0 16/18, P3 16/18
- Full cross-tab: gemma-4-26b x cfpb x B0: 1/3 PASSED, gemma-4-26b x cfpb x P3: 1/3 PASSED
- Consistency: model_pass_sum(32) == r2_passed(32) ✓, cond_pass_sum(32) == r2_passed(32) ✓

### Budget Summary

| Ledger | Reservations | Settlements | Max Committed | Total Settled |
|--------|-------------|-------------|---------------|---------------|
| openrouter-v3-ledger.jsonl (R0+R1) | 188 | 188 | €30.44 | €30.39 |
| openrouter-v3-r2-ledger.jsonl (R2) | 138 | 138 | €23.33 | €23.08 |

## Inconsistencies Found

1. **R0 admission raw events missing**: Claims about R0 admission (3/5 admitted, 2 rejected for route drift) cannot be verified from raw events. Budget ledger confirms 5 R0 reservations but does not record admission outcomes.

2. **R2 pooled vs. disaggregated**: Manuscript reported "10/12 passed" in a condition/dataset table alongside "32/36 passed" pooled. These could not both be full disaggregations of 36 invocations. Root cause: the condition/dataset table was incorrectly computed — it showed only a partial view. **Corrected**: The full cross-tabulation (3 models x 2 datasets x 2 conditions) produces 12 cells with 3 repetitions each, totaling 36. The 10/12 figure was erroneous.

3. **No manifest hash bug**: Python↔Node manifest hash mismatch was fixed (routeUptimeLast5m int/float). Current manifests match.

## Verdict

| Gate | Status |
|------|--------|
| v2 freeze intact | ✓ PASS |
| v3 raw events present | R1 ✓, R2 ✓, R0 ✗ (missing) |
| Tables recompute from raw | R1 ✓, R2 ✓ |
| Consistency checks | R1 ✓, R2 ✓ |
| Budget ledger integrity | ✓ PASS |
| Manifest hashes match | ✓ PASS |
| **Overall** | **CONDITIONAL PASS** — R0 admission claims lack raw event evidence; R1 and R2 are fully verified |
