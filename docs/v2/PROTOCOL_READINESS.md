# Protocol v2 local readiness

Decision: `NOT_FROZEN`.

The platform controls and research pilots are locally validated, both official
datasets are now reproducibly acquired, and all three planned executions of
each admitted frontier model were attempted within the EUR 10 authorization. A
freeze would still be premature because the paper-scale experiment matrix has
not been completed.

| Ordered gate | State | Evidence |
| --- | --- | --- |
| Baseline, unit, fake-secret, fake-provider | Passed | Platform and research test suites; sentinel persistence tests |
| Local Qwen integration and one-record local models | Passed | `results/v2/manifests/local-model-gates.json` |
| Commercial one-record and four-pair smoke | Passed with retained failures | OpenRouter smoke manifests; `results/v2/manifests/four-pair-smoke.json` |
| Forty-record frontier pilot and replication | 15/15 planned attempts completed: 13 released, 2 failed closed; local six-condition matrix incomplete | `docs/v2/FRONTIER_REPLICATION_RESULTS.md`; frontier manifests; preserved `forty-record-multi-model-pilot.jsonl.partial` |
| DP training pilot | Passed | `results/v2/raw/privacy/dp-training-pilot.json` |
| Privacy-attack pilot | Passed | `results/v2/raw/privacy/privacy-attack-pilot.json` |
| Local attack suite and evidence tamper tests | Passed | `results/v2/raw/platform/local-attack-suite.json`; platform v2 tests |
| HMDA and CFPB official assets | Passed | `docs/v2/OFFICIAL_DATASETS.md` and four dataset manifests |
| Protocol freeze | Blocked | Full paper-scale eight-condition execution/evaluation is absent |
| AWS-ready packaging | Not started | Phase 21 follows all local gates and freeze preparation; no AWS deployment is authorized |

The current frontier result is a bounded 40-record governed remote-condition
replication, not a complete eight-condition causal comparison. Claude is
represented by 13 retained failed compatibility attempts and no eligible
forty-record run. One of 13 released attempts showed decision differences in 8
of 20 identical projected pairs, despite an unchanged transmitted hash; this is
reported as execution instability. The results must not be generalized into a
model leaderboard, population fairness claim, or production guarantee.

No `local-protocol-v2-platform` or `local-protocol-v2-benchmark` tag may be
created until the remaining experiment and audit materials are complete. Any
post-freeze change will then require an entry in `docs/PROTOCOL_DEVIATIONS.md`.
