# Governed frontier replication results

Five admitted frontier models received three planned forty-record executions each.
Outputs were released only after native validation; failures remained fail-closed.

| Model | Passed | Failed | Decision stability | Risk-score stability | Mean score range |
| --- | ---: | ---: | ---: | ---: | ---: |
| `google/gemma-4-26b-a4b-it` | 2 | 1 | 0.900 | 0.000 | 31.800 |
| `openai/gpt-5.6-luna` | 3 | 0 | 0.525 | 0.000 | 25.050 |
| `anthropic/claude-opus-4.8` | 0 | 0 | excluded | excluded | excluded |
| `deepseek/deepseek-v4-pro` | 3 | 0 | 1.000 | 1.000 | 0.000 |
| `moonshotai/kimi-k3` | 2 | 1 | 1.000 | 0.550 | 7.700 |
| `meta-llama/llama-4-maverick` | 3 | 0 | 0.700 | 0.650 | 0.350 |

## Attempt-level paired-purpose result

| Model | Repetition | Result | Paired influence |
| --- | ---: | --- | ---: |
| `google/gemma-4-26b-a4b-it` | 1 | released | 0/20 |
| `google/gemma-4-26b-a4b-it` | 2 | released | 0/20 |
| `google/gemma-4-26b-a4b-it` | 3 | failed closed (`JSONDecodeError`) | not released |
| `openai/gpt-5.6-luna` | 1 | released | 0/20 |
| `openai/gpt-5.6-luna` | 2 | released | 8/20 |
| `openai/gpt-5.6-luna` | 3 | released | 0/20 |
| `deepseek/deepseek-v4-pro` | 1 | released | 0/20 |
| `deepseek/deepseek-v4-pro` | 2 | released | 0/20 |
| `deepseek/deepseek-v4-pro` | 3 | released | 0/20 |
| `moonshotai/kimi-k3` | 1 | released | 0/20 |
| `moonshotai/kimi-k3` | 2 | failed closed (`RuntimeError`) | not released |
| `moonshotai/kimi-k3` | 3 | released | 0/20 |
| `meta-llama/llama-4-maverick` | 1 | released | 0/20 |
| `meta-llama/llama-4-maverick` | 2 | released | 0/20 |
| `meta-llama/llama-4-maverick` | 3 | released | 0/20 |

One of 13 released attempts had paired influence: 8 of 260 successful pair observations overall.
The affected GPT-5.6 Luna repetition changed decisions for identical approved projections; its risk scores stayed equal within each pair. Because the transmitted record hash was unchanged and prohibited fields were absent, this is evidence of execution instability rather than evidence that prohibited fields were used.

## Execution and budget

- Planned attempts: 15.
- Passed: 13; failed closed: 2.
- Conservative three-attempt debit: EUR 0.64814882.
- Cumulative conservative ledger: EUR 7.90239384 of EUR 10.0.
- Remaining authorization: EUR 2.09760616.

## Interpretation boundary

- This is a 40-record governed remote replication, not a full condition matrix or population estimate.
- Stability metrics compare successful outputs only; failed calls remain visible separately.
- A deterministic decision does not imply a calibrated or correct risk score.
- Claude is excluded because no strict ZDR smoke gate passed.
- Remote processing occurred through OpenRouter under pinned ZDR routes.
