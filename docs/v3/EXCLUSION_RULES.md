# Exclusion Rules

**Status**: FROZEN (Gate 3, 2026-08-05)

## Pre-Registered Exclusion Criteria

### 1. Route Drift (R0 Admission)

- **Rule**: If the upstream route assignment changes between metadata captures, the model is excluded from admission.
- **Rationale**: Route drift breaks the integrity chain and prevents silent provider substitution.
- **Affected**: openai/gpt-5.6-luna, meta-llama/llama-4-maverick (excluded in diagnostic).
- **Documentation**: Recorded in `docs/v3/OPENROUTER_ADMISSION.md`.

### 2. Timeout (Execution)

- **Rule**: If an invocation exceeds the registered timeout (30 seconds), it is excluded from per-protocol analysis but retained in intent-to-execute.
- **Rationale**: Timeout indicates infrastructure failure, not model behavior.
- **Documentation**: Recorded in raw events with `status=TIMEOUT`.

### 3. Infrastructure Failure (Execution)

- **Rule**: If an invocation fails due to provider error (5xx, rate limit, network), it is excluded from per-protocol analysis but retained in intent-to-execute.
- **Rationale**: Infrastructure failure is outside the model's control.
- **Documentation**: Recorded in raw events with `status=INFRASTRUCTURE_FAILURE`.

### 4. Manifest Hash Mismatch (Verification)

- **Rule**: If the response manifest hash does not match the captured manifest, the invocation is excluded from per-protocol analysis.
- **Rationale**: Hash mismatch indicates tampering or route substitution.
- **Documentation**: Recorded in verification logs.

### 5. Budget Exhaustion (Budget)

- **Rule**: If the budget ledger shows committed amount exceeding the authorized ceiling, no further invocations are permitted.
- **Rationale**: Budget enforcement prevents runaway costs.
- **Documentation**: Recorded in budget ledger.

## Post-Hoc Exclusion Criteria

### 6. Duplicate Invocation

- **Rule**: If the same pair, condition, model, and repetition are invoked more than once, only the first invocation is retained.
- **Rationale**: Duplicates may bias results.
- **Documentation**: Detected during data cleaning.

### 7. Malformed Response

- **Rule**: If the model response cannot be parsed as valid JSON or lacks required fields, the invocation is excluded.
- **Rationale**: Malformed responses cannot be evaluated.
- **Documentation**: Recorded in raw events with `status=MALFORMED`.

## Exclusion Reporting

- **CONSORT-style flow**: Number of pairs → number of invocations → exclusions → per-protocol population.
- **Transparency**: All exclusions documented with reason codes.
- **Sensitivity**: Primary analysis repeated with and without excluded cases.
