# Governed frontier pilot results

Captured: 2026-08-04

Five models passed both the one-record gate and the 40-record governed pilot.
No Claude model reached the pilot: Claude Opus 5, Sonnet 5, and Opus 4.8 all
failed at OpenRouter's provider layer under the required ZDR, no-fallback, and
strict structured-output controls. Those failures remain append-only evidence;
they were not converted into model results.

The deterministic comparison artifact is
`results/v2/derived/openrouter-frontier-pilot-comparison.json`, with comparison
hash `f6ed1455494443903399e7f48f3064695dd8d8638971ae0c92a39b662a452798`.

## Validated model results

| Model | Manual review | Mean risk score | Tokens | Duration | Conservative debit |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gemma 4 26B A4B | 22/40 (55%) | 34.50 | 11,476 | 7.091 s | EUR 0.00147432 |
| GPT-5.6 Luna | 24/40 (60%) | 49.10 | 8,376 | 3.711 s | EUR 0.00979600 |
| DeepSeek V4 Pro | 30/40 (75%) | 4.00 | 9,220 | 10.543 s | EUR 0.01677708 |
| Kimi K3 | 26/40 (65%) | 48.15 | 8,764 | 8.641 s | EUR 0.02974800 |
| Llama 4 Maverick | 18/40 (45%) | 0.50 | 8,574 | 9.686 s | EUR 0.00199020 |

Risk-score magnitudes are not comparable across models: DeepSeek used a 1-5
range, Llama used 0-1, and the other models used broader scales. The table
reports what each model returned and does not treat those values as calibrated
probabilities.

## Paired-purpose result

Every model returned the same decision and the same risk score within all 20
pairs. The paired variants differ only in six prohibited synthetic internal
fields; those fields were denied before transmission. The 100% within-pair
agreement therefore validates this pilot's purpose-based projection boundary.
It is not a general fairness result because the approved public fields are
identical within each pair.

## Cross-model result

Only 12 of 40 records (30%) received a unanimous decision across the five
passing models. Pairwise decision agreement ranged from 45% (Gemma versus GPT
Luna) to 90% (DeepSeek versus Kimi). The five-model majority selected
`MANUAL_REVIEW` for 26 records and `STANDARD_REVIEW` for 14.

Risk-score rank correlations ranged from approximately -0.280 to 0.449. This
shows substantial model-dependent ordering on the same approved projection,
but the sample is too small for a performance or superiority claim.

## Cost and execution boundary

- Hard authorization: EUR 10.00.
- Conservative append-only debit after all diagnostics and pilots: EUR
  7.31403062.
- Remaining authorization: EUR 2.68596938.
- Incremental conservative debit for the five completed 40-record pilots: EUR
  0.05978560.
- Known provider-reported charge across successful smoke and pilot calls:
  0.06279612 OpenRouter credits. Failed calls without provider cost evidence
  retain their full EUR 0.25 reservations in the conservative ledger.

USD-denominated manifest rates are treated as EUR at parity only for the hard
ceiling. OpenRouter's reported account charge remains separately labelled and
is not silently converted to EUR.

## Interpretation limit

These results validate governed remote execution, model substitution controls,
purpose-field denial, native output release, and evidence capture on a
40-record diagnostic sample. They are not a population estimate, a benchmark
leaderboard, a general fairness guarantee, or a paper freeze result.
