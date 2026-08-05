# Power analysis

Status: prospective, before v3 confirmatory outcomes  
Independent units: 200 public-source base-record pairs, 100 per dataset

## Pilot evidence and why it is not the effect estimate

The frozen v2 controlled condition pilot observed paired action influence in
4/4 pairs for its all-data condition and 0/4 for each of three successful
projected conditions. The prompt-only call failed. Each condition had a single
eight-record invocation. These data establish plumbing and sensitivity only;
using 100% versus 0% as a confirmatory effect assumption would be severely
optimistic. No v2 observation is included in v3 hypothesis tests.

The v2 position and repetition diagnostics also showed material output
instability. Consequently, model repetitions are blocked repeated measures and
not counted as new independent pairs.

## Primary paired-outcome calculation

The exact prospective calculation uses McNemar's conditional binomial test. Let
\(p_{10}\) be the probability that the weak baseline violates Task B while P3
does not, and \(p_{01}\) the reverse. Conditional on the number of discordant
pairs, the null success probability is 0.5. Power sums the alternative binomial
rejection probability over the binomial distribution of the discordant count.

For H4 there are two primary comparisons, so the conservative calculation uses
two-sided \(\alpha=0.025\), the first Holm threshold.

| Scenario | \(p_{10}\) | \(p_{01}\) | Absolute paired difference | Power at 80 pairs | Power at 100 pairs | Power at 200 pooled pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| H4 strong but plausible | 0.20 | 0.05 | 0.15 | 0.628 | 0.759 | 0.983 |
| H4 conservative | 0.14 | 0.04 | 0.10 | 0.372 | 0.480 | 0.861 |

Under the conservative H4 assumption, 175 independent pairs reach 80% power.
The registered 200-pair pooled analysis exceeds that requirement. The 100-pair
dataset-specific estimates are intentionally treated as heterogeneity analyses,
not separate powered success claims.

## Approved-utility sensitivity

For the Task A public-only versus authorized-oracle gate, the planning scenario
assumes \(p_{10}=0.16\) (oracle correct/public wrong) and \(p_{01}=0.06\)
(public correct/oracle wrong), a net paired accuracy gain of 0.10. A one-sided
exact McNemar test at \(\alpha=0.05\) has estimated power 0.534 at 80 pairs,
0.633 at 100, and 0.906 at 200. The smallest sample reaching 80% power is 146
pairs. Thus the pooled 200-pair sensitivity gate is powered; individual datasets
are not.

Balanced accuracy rather than raw accuracy is the registered Task A utility, so
the exact McNemar calculation is an approximation to the stratified estimator.
The final test uses a pair-level stratified permutation/bootstrap procedure.
The approximation is retained because it makes the binary discordance
assumptions transparent and is conservative under balanced strata.

## Precision when no P3 influence is observed

With zero events in 200 independent pairs, the two-sided 95% Clopper–Pearson
upper bound is approximately 1.83%. With zero events in only 100 pairs it is
approximately 3.62%. These are finite-sample bounds, not proof of zero risk.
Dependence induced by batching or model repetitions is handled by pair-level
cluster resampling; the nominal binomial bound is reported only for the primary
pair/model specification.

## Attack-suite precision

The attack suite has many distinct mechanisms rather than repeated draws from a
single population. It is not valid to claim that 50 attack IDs equal a random
sample of all attacks. Primary inference compares paired outcomes for B2 and P3
over the exact registered attack instances and repetitions, stratified by attack
family. Family results are coverage measurements of this suite. Exact binomial
bounds are shown for repeated attacks, but external generalization remains
qualitative.

Each deterministic attack is repeated three times only to detect state/lifecycle
bugs. Identical repetitions do not multiply the conceptual attack coverage.

## DP experiments

DP training uses at least ten preregistered training seeds per configuration.
The unit is a complete train/evaluate run. Because privacy-attack variance is
unknown and v2 inputs were controlled validation fixtures rather than empirical
samples, the DP study reports paired bootstrap intervals and standardized effect
sizes; it does not claim a prospectively powered universal leakage effect. D2
must meet the registered utility margin and show directionally lower empirical
risk to support H9.

## Attrition and expansion rule

The sample is 200 valid pairs after deterministic dataset validation, not 200
attempted downloads. A pair may be excluded only before model execution for a
preregistered reason: duplicate base record, missing required public fields,
pair-integrity failure, or class-stratum overflow. The exclusion manifest is
frozen.

No outcome-based replacement is allowed. Provider/model failures remain in
availability denominators. Increasing the pair count after observing v3
condition outcomes is prohibited; a future expansion must be a new protocol
version with separate confirmatory analysis.

## Reproduction

The executable power calculation is implemented in
`src/purposebench/v3/power.py`; `scripts/run_v3_power_analysis.py` emits the
canonical JSON used to verify the values above. It uses no v3 outcome data.
