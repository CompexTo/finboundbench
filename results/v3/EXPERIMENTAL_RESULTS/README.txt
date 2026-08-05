EXPERIMENTAL RESULTS SUMMARY
============================
Created: 2026-08-05 21:20:59

FILES:
------
1. confirmatory-reduced-events.jsonl - 330 events (40 pairs/dataset, gemma-4-26b)
2. confirmatory-reduced-budget.jsonl - Budget ledger for reduced-scope run
3. attack-suite-events.jsonl - 235 attack events (57 attacks x conditions)
4. attack-report.json - Attack outcomes (71.5% prevention, 75.7% detection)
5. dp-experiments-events.jsonl - 40 DP experiment events (D0-D3)
6. dp-report.json - DP privacy-utility tradeoffs
7. evidence-verification-events.jsonl - 20 evidence verification events
8. evidence-report.json - Evidence coverage (100%)
9. availability-overhead-events.jsonl - 350 availability/overhead events
10. availability-overhead-report.json - Availability (98.6%), Overhead (1.31x)
11. statistical-report.json - Computed metrics (AUR, UIR, SPCR, EVC)
12. v3-final-freeze.json - Final freeze manifest

KEY METRICS:
------------
- AUR (Authorized Utility Retention): 0.9341
- UIR (Unauthorized Influence Rate): 0.2000
- SPCR (Silent Policy Compromise Rate): 0.2426
- EVC (Evidence Coverage): 1.0000
- Availability: 0.9857
- Overhead: 1.3116x

LIMITATIONS:
------------
- All security metrics from test-double oracles
- Live execution required for definitive claims
- kimi-k3 and deepseek-v4-pro rate-limited
