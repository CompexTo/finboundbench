# Protocol v2 local readiness

Decision: `FROZEN_WITH_LIMITATIONS`.

The local implementation and bounded remote-pilot evidence snapshot is frozen.
This is not a claim that the paper-scale eight-condition study is complete.
The freeze is scoped to the exact artifacts in
`results/v2/manifests/protocol-v2-local-freeze.json`; material changes require
a protocol deviation and a new manifest.

| Ordered gate | State | Evidence |
| --- | --- | --- |
| Baseline, unit, fake-secret, fake-provider | Passed | Platform and research test suites; sentinel persistence tests |
| Official HMDA and CFPB assets | Passed | `docs/v2/OFFICIAL_DATASETS.md` and four source/transformation manifests |
| Local model gates | Passed | `results/v2/manifests/local-model-gates.json` |
| OpenRouter-only provider policy | Passed | Phase-two config; ZDR, pinned routes, no fallback, only `OPENROUTER_API_KEY` |
| Claude compatibility | Closed after retained fail-closed Gate 1 | `results/v2/derived/openrouter-claude-closure.json` |
| Eligible position diagnostic | Completed with one retained model failure | GPT-5.6 Luna passed 11 layouts; DeepSeek V4 Pro failed closed |
| Reduced governed matrix | Completed with one retained model failure | GPT-5.6 Luna, Kimi K3, and Llama 4 passed; Gemma 4 failed closed after smoke |
| Controlled five-condition pilot | Four passed, one retained rate-limit failure | `results/v2/derived/openrouter-full-condition-pilot.json` |
| DP training and privacy-attack validation | Passed | Current phase-two CPU artifacts under `results/v2/raw/privacy/` |
| Local attack suite | Passed | 17 attacks; 123 API tests and 32 runner tests |
| Evidence audit | Passed with retained failures | `results/v2/derived/protocol-v2-local-evidence-audit.json` |
| Scoped protocol freeze | Frozen with limitations | Hash manifest plus this readiness decision |
| AWS/Nitro deployment | Not authorized or performed | Hardware-attested execution remains future work |

The final conservative OpenRouter ledger is EUR 9.01262918 against an absolute
EUR 12.90239384 authorization. The added EUR 5 authorization consumed EUR
1.11023534, leaving EUR 3.88976466 unused. All 30 phase-two reservations have
matching settlements. Across the audited phase-two raw artifacts there were 29
provider calls, zero retries, zero fallbacks, 25 released successes, and four
fail-closed records.

The remaining paper-readiness gap is the predeclared paper-scale condition
matrix. In particular, the prompt-only pilot invocation was rate-limited, the
local six/eight-condition matrix was not executed at paper scale, and the
bounded results cannot establish population effects, causal effects, a model
leaderboard, a fairness guarantee, or production fitness. The trusted-host
model also excludes a malicious host administrator.

No Git tag was created. The user requested local commits, not pushes, and this
freeze is represented by committed protocol, audit, result, and hash-manifest
artifacts.
