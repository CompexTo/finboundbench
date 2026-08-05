# Limitations

**Status**: FROZEN (Gate 3, 2026-08-05)

## Scope Limitations

1. **Non-TEE protocol**: The system trusts the host and cannot prevent a malicious administrator from reading memory, altering execution below the measured boundary, or denying service.

2. **Paired tests only**: The protocol detects registered forms of influence, not every semantic or covert channel.

3. **Model/provider constraints**: Model versions, route behavior, batching, and stochasticity constrain external validity.

4. **DP limitations**: DP accountant values do not alone establish empirical privacy.

5. **Attack exhaustion**: Attack measurements do not exhaust possible adversaries.

## Data Limitations

6. **Semi-synthetic data**: Public records with synthetic confidential signals; does not model real internal customer facts.

7. **Ecological validity**: Semi-synthetic construction improves causal control but limits ecological validity.

8. **Historical outcomes**: Historical public outcomes may reflect institutional and social processes; not treated as normative targets.

9. **Protected-group fairness**: Protected-group fairness and regulatory compliance are outside the claims.

## Statistical Limitations

10. **Sample size**: 100 pairs per dataset may not detect small effects.

11. **Multiple comparisons**: Holm adjustment reduces power for secondary analyses.

12. **Permutation tests**: Paired permutation tests assume exchangeability under the null.

13. **Bootstrap CIs**: Bootstrap confidence intervals may be conservative for small samples.

## Implementation Limitations

14. **OpenRouter dependency**: The protocol depends on OpenRouter for model access; provider failures may affect results.

15. **Route drift**: Route drift may exclude models from admission.

16. **Budget constraints**: Budget ceiling limits the number of invocations.

17. **No TEE**: No hardware attestation or TEE is used; all security is software-based.

## Negative Results

18. **Retained**: Negative, failed, and inconclusive results are retained and reported.

19. **No publication bias**: All registered hypotheses are reported regardless of outcome.

20. **Transparency**: All artifacts, budgets, and claim traces are frozen.
