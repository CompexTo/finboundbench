# Cost Plan

**Status**: FROZEN (Gate 3, 2026-08-05)

## Observed Costs (Diagnostic Phase)

| Phase | Invocations | Committed (EUR) | Settled (EUR) |
|-------|-------------|-----------------|---------------|
| R0 + R1 | 188 | 30.44 | 30.39 |
| R2 | 138 | 23.33 | 23.08 |
| **Total** | **326** | **53.77** | **53.47** |

## Projected Costs (Confirmatory Phase)

### Per-Invocation Cost Estimate

- **Observed average**: €0.16 per invocation (€53.47 / 326 invocations).
- **Range**: €0.02–0.05 per invocation (varies by model and dataset).
- **Conservative estimate**: €0.04 per invocation.

### Full 200-Pair Run

| Parameter | Value |
|-----------|-------|
| Pairs per dataset | 100 |
| Datasets | 2 (HMDA + CFPB) |
| Repetitions | 3 |
| Conditions | 11 (B0–B3, P0–P3, D0–D3) |
| Models | 3 |
| **Total invocations** | **19,800** |
| **Estimated cost** | **€792** (at €0.04/invocation) |

### Budget Ceiling

- **Hard ceiling**: €1,000.
- **Contingency**: 20% (€200) for retries, failures, and route drift.
- **Remaining budget**: €1,000 − €53.47 = €946.53.

## Cost Monitoring

- **Real-time ledger**: `results/v3/raw/budget/openrouter-v3-ledger.jsonl`.
- **Reservation-per-call**: €0.05 (conservative upper bound).
- **Settlement**: Actual cost debited after invocation.
- **Failure policy**: Conservative debit on failure (full reservation amount).

## Cost Control Mechanisms

1. **Pre-invocation check**: Budget committed must be < ceiling before each reservation.
2. **Post-invocation settlement**: Actual cost replaces reservation debit.
3. **Failure handling**: Timeout or infrastructure failure → full reservation debited.
4. **Route drift**: Excluded from admission → no cost incurred.
5. **Manual override**: Budget ceiling can only be raised by user instruction.

## Cost Reporting

- **Per-phase summary**: Committed vs settled by phase.
- **Per-model breakdown**: Cost by model across all phases.
- **Per-dataset breakdown**: Cost by dataset across all phases.
- **Cumulative tracking**: Running total against ceiling.
