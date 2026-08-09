# results/v4 — Directory layout

Protocol v4 results tree. Each directory has a defined purpose; agents write
only into their owned directories (ownership: `CONTRACT_V4.md` §9).

| Directory | Contents |
|-----------|----------|
| `eligibility/` | Eligibility run outputs: per-lane/task gate JSON (`model-task-eligibility.json`), the frozen negative-evidence pointer (`NEGATIVE_MODEL_TASK_ELIGIBILITY_RESULT.md`), raw eligibility events, budget ledger. |
| `calibration/` | Development/calibration outputs from `data/v4/v4_calibr/` — generator sanity, signal-strength sensitivity. **Never** confirmatory. |
| `confirmatory/` | Confirmatory run events (`CONFIRMATORY` pairs only), raw outputs, per-lane repetition data. |
| `attacks/` | Cross-layer security / attack-family results (later phase, after main freeze). |
| `privacy/` | Real-DP experiments (later phase, separate protocol). |
| `evidence/` | Lifecycle / evidence-bundle verification outputs. |
| `performance/` | Latency, provider calls, tokens, monetary cost per lane/task/condition (provider vs behavioral separated). |
| `statistics/` | Pre-registered analysis outputs: `eligibility-report.json`, `power-estimate.json`, bootstrap/permutation tables. |
| `manifests/` | Frozen manifests incl. `v4-signal-freeze.json` (owned by Agent 2), run manifests, hashes. |

Naming rules: no file inside `results/v4` may overwrite a `results/v3/**` file;
`results/v3/**` is immutable. Derived numbers are rebuilt from raw events
before freeze (v3 rule carried forward, `docs/v3/FINBOUNDBENCH_SPEC.md` §7).

See also `docs/v4/PROTOCOL-v4-purpose-selectivity.md` for the full protocol.