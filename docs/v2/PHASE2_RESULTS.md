# Phase-two bounded benchmark results

## Outcome

The local implementation and bounded OpenRouter research phase completed its
authorized gates. The evidence audit passed with four retained fail-closed
remote records. These results are diagnostic pilots, not a paper-scale study or
a production certification.

## Model lanes

| Model | Bounded result | Conservative debit |
| --- | --- | ---: |
| Anthropic Claude Opus 5 | Gate 0 passed locally; the single corrected Gate 1 provider call failed closed with `PROVIDER_ROUTING`; lane formally closed | EUR 0.50000000 |
| OpenAI GPT-5.6 Luna | Passed all 11 position layouts and all reduced-matrix invocations | EUR 0.08726400 across position and reduced lanes |
| DeepSeek V4 Pro | First eligible position invocation failed closed; no retry and no reduced-matrix admission | EUR 0.05000000 |
| Google Gemma 4 26B | One-record smoke passed; first 40-record invocation failed closed; no retry | EUR 0.10007974 |
| Moonshot Kimi K3 | Passed smoke and two 40-record repetitions; selected for the condition pilot | EUR 0.11769900 in the reduced lane |
| Meta Llama 4 Maverick | Passed smoke and two 40-record repetitions | EUR 0.00573160 |

GPT-5.6 Luna's repeatedly observed position cases had 50% governed-action
stability, a mean score range of 0.245, and a maximum score range of 0.34. In
the two-run reduced matrix, governed-action repetition agreement was 65% for
GPT-5.6 Luna, 95% for Kimi K3, and 60% for Llama 4 Maverick. Every passing
model had 0 of 20 paired-purpose action changes in each projected repetition.
Cross-model action agreement ranged from 47.5% to 85%, reinforcing that scores
are not calibrated across models and that this is not a leaderboard.

## Controlled condition pilot

Kimi K3 was tested once per condition on four HMDA-derived pairs (eight public
records) with synthetic internal fields where explicitly consented. Identifiers
were pseudonymized, routes were pinned and ZDR-required, and each successful
output passed native Compex release validation.

| Condition | Result | Paired action influence |
| --- | --- | ---: |
| All data, no purpose policy | Passed | 4/4 pairs (100%) |
| Prompt-only purpose restriction | Failed closed: provider rate limit | Not observed |
| Ordinary metadata prefilter | Passed | 0/4 pairs |
| Compex governed projection | Passed | 0/4 pairs |
| Compex projection plus native release | Passed | 0/4 pairs |

The all-data condition's mean within-pair score difference was 0.83 (maximum
0.84); the three successful projected conditions had zero within-pair score
difference. Because each condition had only one eight-record invocation and
the prompt-only condition failed, these observations do not identify a causal
effect and must not be generalized to a population.

## Privacy and security

The deterministic CPU DP training validation reproduced four configurations.
Non-DP accuracy was 0.872549. Weak, medium, and stronger DP had actual Opacus
epsilon values of 13.274465, 5.161475, and 2.496839 at delta 0.00001, with
accuracies of 0.852941, 0.852941, and 0.862745 respectively. Secure RNG was
disabled for this research validation, so production training would require a
new secure-mode run.

The controlled privacy-attack validation produced 15 measurements and five
comparisons. Governance alone did not change the supplied empirical risk
observations; the DP condition reduced them. This validates the attack and
comparison plumbing over controlled inputs, not universal leakage prevention.

The refreshed local platform suite passed all 17 attack classes, 123 targeted
API tests, and 32 runner tests against platform commit
`29e4b2ea96f75263dc8fea82c41b4273be7ad7f3`.

## Cost and provider controls

The append-only ledger committed EUR 9.01262918 of the EUR 12.90239384 absolute
authorization. Only EUR 1.11023534 of the added EUR 5 authorization was used.
The phase had 30 reservations and 30 settlements. The audited raw evidence has
29 provider calls, zero automatic retries, and zero fallbacks. All commercial
calls used OpenRouter; no direct commercial-provider API was used. The secret
scan found zero API-key value hits in tracked files or Git history and recorded
neither the key nor its hash.
