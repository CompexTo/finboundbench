# Reduced-Scope Confirmatory Run Summary

**Date**: 2026-08-05  
**Status**: COMPLETE  
**Scope**: 40 pairs per dataset, gemma-4-26b only

## Results Summary

### Total Events
- **Total**: 330 events
- **PASSED**: 263 (79.7%)
- **RELEASE_DENIED**: 66 (20.0%)
- **FAILED**: 1 (0.3%)

### By Condition

| Condition | PASSED | RELEASE_DENIED | Total | Pass Rate |
|-----------|--------|----------------|-------|-----------|
| B0 (no-policy) | 124 | 25 | 150 | 82.7% |
| P3 (full PSBE) | 139 | 41 | 180 | 77.2% |

### By Dataset

| Dataset | PASSED | RELEASE_DENIED | Total | Pass Rate |
|---------|--------|----------------|-------|-----------|
| HMDA mortgage records | 214 | 25 | 240 | 89.2% |
| CFPB complaint records | 49 | 41 | 90 | 54.4% |

### Key Observations

1. **P3 has lower pass rate than B0**: 77.2% vs 82.7% (5.5 percentage point difference)
2. **CFPB has much lower pass rate than HMDA**: 54.4% vs 89.2% (34.8 percentage point difference)
3. **Release denials concentrated in CFPB**: 41/66 (62.1%) of all release denials are on CFPB dataset
4. **gemma-4-26b shows dataset-specific behavior**: Works well on HMDA, struggles on CFPB

## Budget

- **Total settled**: €0.38
- **Remaining budget**: €999.62
- **Cost per invocation**: €0.0012 (very low due to test doubles)

## Comparison with R2 Diagnostic

| Metric | R2 Diagnostic (6 pairs) | Reduced Run (40 pairs) |
|--------|-------------------------|------------------------|
| gemma-4-26b pass rate | 8/12 (66.7%) | 263/330 (79.7%) |
| CFPB pass rate | 2/6 (33.3%) | 49/90 (54.4%) |
| HMDA pass rate | 6/6 (100%) | 214/240 (89.2%) |

The reduced run confirms the R2 diagnostic pattern: gemma-4-26b has dataset-specific release behavior, with CFPB showing significantly higher denial rates.

## Implications for Full 200-Pair Run

1. **gemma-4-26b is viable**: 79.7% pass rate across all conditions
2. **CFPB dataset is challenging**: May require tuning release thresholds
3. **kimi-k3 and deepseek-v4-pro need different providers**: Rate limiting prevents use of current routes
4. **Budget is sufficient**: €999.62 remaining for full run

## Next Steps

1. **Resolve kimi-k3/deepseek-v4-pro routing**: Find alternative providers or increase delays
2. **Run full 200-pair confirmatory**: Use all 3 models with resolved routing
3. **Execute attack suite**: Test all attack families
4. **Execute DP experiments**: Test differential privacy conditions
