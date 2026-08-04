# Governed OpenRouter frontier matrix

Captured: 2026-08-04

This research-owned matrix evaluates the same pseudonymized, purpose-approved
projection through six current OpenRouter catalog IDs. Compex remains
model-neutral: the research manifest supplies model identity, capabilities,
and the conservative price table.

| Family | Requested model ID | Catalog canonical slug |
| --- | --- | --- |
| Gemma 4 | `google/gemma-4-31b-it` | `google/gemma-4-31b-it-20260402` |
| GPT Luna | `openai/gpt-5.6-luna` | `openai/gpt-5.6-luna-20260709` |
| Claude | `anthropic/claude-opus-5` | `anthropic/claude-opus-5-20260723` |
| DeepSeek | `deepseek/deepseek-v4-pro` | `deepseek/deepseek-v4-pro-20260423` |
| Kimi | `moonshotai/kimi-k3` | `moonshotai/kimi-k3-20260715` |
| Llama | `meta-llama/llama-4-maverick` | `meta-llama/llama-4-maverick-17b-128e-instruct` |

The callable IDs deliberately exclude moving `latest`, `preview`, `default`,
and automatic-router aliases. OpenRouter's canonical slugs are retained as
catalog-version evidence even though the catalog does not accept those slugs as
callable IDs. Every response must echo the exact requested model ID or the
platform rejects it as substitution.

## Controlled execution

- Phase 1 runs one record per model. A model must pass strict structured-output,
  exact-model, release, disclosure, and evidence checks before its 40-record run
  is eligible for interpretation.
- Phase 2 runs the 20 complete paired cases (40 records) once per passing model.
- Reasoning is explicitly disabled when the model advertises the OpenRouter
  reasoning parameter. The hashed research manifest binds whether the request
  uses `enabled: false` or `effort: none`; unsupported sampling parameters are
  omitted and the provider must support every parameter actually transmitted.
- Provider fallback is disabled. Routing requires zero data retention and
  denies providers that collect request data. Each model also pins one exact
  ZDR-capable upstream endpoint slug and its endpoint-metadata hash; this avoids
  silently changing the host implementation while keeping OpenRouter as the
  single allowlisted network destination.
- The selected projection is pseudonymized before the one allowlisted HTTPS
  call. Synthetic internal fields are denied and never transmitted.

## Cost boundary

The cumulative authorization is EUR 10. The first failed sweep reserved EUR
0.50 per attempt and conservatively retained EUR 3.00. Subsequent attempts
reserve EUR 0.25 in an append-only ledger. A successful attempt settles to the conservative
manifest-derived token cost; an attempt without complete cost evidence retains
the entire reservation as a debit. The ledger rejects a new reservation when
it would cross EUR 10.

For the ceiling only, one USD is treated as one EUR. Successful evidence also
records OpenRouter's reported account charge separately in OpenRouter credits.
After the retained first-sweep debit, the planned retry and pilot calls reserve
at most another EUR 3 before settlement, leaving bounded diagnostic headroom
while preserving the absolute EUR 10 stop.

These runs validate governed remote processing and compare model behavior. They
do not show that the transmitted projection remained local, and smoke or pilot
results are not paper claims.

## Retained smoke checkpoint

The second sweep produced complete, validated one-record results for GPT-5.6
Luna, Kimi K3, and Llama 4 Maverick. Gemma 4 and DeepSeek V4 Pro returned
provider HTTP 429 from their pinned routes, while Claude Opus 5 returned HTTP
400. All three failures remain in their append-only partial streams. After
settling the successful calls to their conservative token costs, the cumulative
ledger debit is EUR 3.7532468. No pilot interpretation is allowed until each
model's smoke gate passes.

Claude's first manifest-bound `EFFORT_NONE` attempt also returned HTTP 400 and
is retained. The cumulative ledger debit after that no-cost-evidence failure is
EUR 4.0032468. A generic platform correction now retains only OpenRouter's
typed error category, provider code, and response-body hash so a subsequent
diagnostic attempt can distinguish invalid input from policy or capacity errors
without retaining the provider's free-text message.
