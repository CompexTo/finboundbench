# Governed frontier pilot results

These deterministic summaries are regenerated from hash-validated raw JSONL.
The remote projection was processed by OpenRouter and did not remain local.

| Model | Route | Paired influence | Decision agreement | Risk-score agreement | Seconds | Conservative EUR |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `google/gemma-4-26b-a4b-it` | `nextbit/bf16` | 0.000 | 1.000 | 1.000 | 7.091 | 0.00147432 |
| `openai/gpt-5.6-luna` | `azure` | 0.000 | 1.000 | 1.000 | 3.711 | 0.00979600 |
| `deepseek/deepseek-v4-pro` | `parasail/fp8` | 0.000 | 1.000 | 1.000 | 10.543 | 0.01677708 |
| `moonshotai/kimi-k3` | `morph` | 0.000 | 1.000 | 1.000 | 8.641 | 0.02974800 |
| `meta-llama/llama-4-maverick` | `deepinfra/base` | 0.000 | 1.000 | 1.000 | 9.686 | 0.00199020 |

## Exclusions

- `anthropic/claude-opus-4.8`: no forty-record run; its strict smoke gate failed after 1 retained attempt(s). The Claude family accumulated 13 retained failed attempts across three model IDs.

## Interpretation boundary

- This is a governed remote-processing pilot, not a population estimate.
- Paired influence covers decision or numeric risk-score changes.
- Claude is excluded because no strict ZDR smoke gate passed.
- Provider costs use OpenRouter credits; budget debits use USD/EUR parity.
