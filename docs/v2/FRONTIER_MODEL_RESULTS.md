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
- Conservative append-only debit after the initial pilots: EUR 7.31403062.
- Conservative append-only debit after all three planned executions: EUR
  7.90239384.
- Remaining authorization: EUR 2.09760616.
- Incremental conservative debit for the five completed 40-record pilots: EUR
  0.05978560.
- Conservative debit across all 15 planned pilot/replication attempts: EUR
  0.64814882, including EUR 0.50 retained for two failures without cost
  evidence.
- Known provider-reported charge across successful smoke and pilot calls:
  0.06279612 OpenRouter credits. Failed calls without provider cost evidence
  retain their full EUR 0.25 reservations in the conservative ledger.

USD-denominated manifest rates are treated as EUR at parity only for the hard
ceiling. OpenRouter's reported account charge remains separately labelled and
is not silently converted to EUR.

## Three-execution replication

All 15 planned executions were attempted without retries. Thirteen released a
validated output; Gemma repetition 3 returned truncated JSON and Kimi
repetition 2 returned invalid choices, so both failed closed and retained their
full EUR 0.25 reservations. Claude remained ineligible and received no pilot
reservation.

| Model | Released | Failed closed | Exact decision stability | Exact risk-score stability |
| --- | ---: | ---: | ---: | ---: |
| Gemma 4 26B A4B | 2 | 1 | 90.0% | 0.0% |
| GPT-5.6 Luna | 3 | 0 | 52.5% | 0.0% |
| DeepSeek V4 Pro | 3 | 0 | 100.0% | 100.0% |
| Kimi K3 | 2 | 1 | 100.0% | 55.0% |
| Llama 4 Maverick | 3 | 0 | 70.0% | 65.0% |

These stability rates compare each record across that model's successful
executions. Only DeepSeek reproduced every decision and score exactly. Exact
decision counts alone can conceal record-level changes: Gemma returned the same
aggregate decision counts in both successful runs but changed four individual
records.

Twelve of thirteen released executions retained zero within-pair influence.
GPT-5.6 Luna repetition 2 changed the decision in 8 of 20 identical approved
projections while keeping each pair's risk score equal; repetitions 1 and 3 had
zero influence. The transmitted projection hash did not change and prohibited
fields were absent, so this is treated as execution instability, not evidence
that prohibited fields were transmitted or used. Full validated attempt data
is in `results/v2/derived/openrouter-frontier-replication.json`.

## Interpretation limit

These results validate governed remote execution, model substitution controls,
purpose-field denial, native output release, and evidence capture on a
40-record diagnostic sample. Three planned executions improve the stability
diagnostic but do not add the missing experimental conditions. These are not a
population estimate, benchmark leaderboard, general fairness guarantee, or
paper freeze result.
