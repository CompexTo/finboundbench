# Evidence Study

**Status**: FROZEN (Gate 3, 2026-08-05)

## Evidence Bundle Components

### 1. Contract Evidence

- **Component**: Immutable purpose contract tuple.
- **Fields**: Identity, purpose, dataset binding, projection, workload, model, capabilities, release predicate, privacy budget, lifecycle, evidence contract.
- **Verification**: SHA-256 hash of contract matches captured manifest.

### 2. Dataset/Projection Evidence

- **Component**: Deterministic approved projection.
- **Fields**: Dataset hash, projection parameters, selected fields.
- **Verification**: Projection is deterministic and reproducible.

### 3. Workload/Model Evidence

- **Component**: Workload and model identity.
- **Fields**: Workload hash, model ID, route, manifest hash.
- **Verification**: Manifest hash matches captured manifest.

### 4. Capability Evidence

- **Component**: Capability decisions.
- **Fields**: Allowed capabilities, denied capabilities, capability hash.
- **Verification**: Capability decisions match contract.

### 5. Privacy Ledger Evidence

- **Component**: Privacy budget accounting.
- **Fields**: Epsilon spent, delta spent, budget remaining.
- **Verification**: Ledger is internally consistent.

### 6. Release Decision Evidence

- **Component**: Release predicate evaluation.
- **Fields**: Release decision, reason code, predicate hash.
- **Verification**: Release decision matches contract.

### 7. Event Chain Evidence

- **Component**: Execution event log.
- **Fields**: Timestamps, status codes, hashes.
- **Verification**: Event chain is complete and hash-linked.

## Mandatory Claims

| Claim | Description | Verification |
|-------|-------------|--------------|
| Contract integrity | Contract hash matches manifest | SHA-256 comparison |
| Projection integrity | Projection is deterministic | Reproducibility check |
| Model integrity | Model ID and route match manifest | Manifest comparison |
| Capability integrity | Capabilities match contract | Capability check |
| Privacy integrity | Budget is not exhausted | Ledger check |
| Release integrity | Release decision is correct | Predicate evaluation |
| Evidence integrity | Event chain is complete | Hash chain verification |

## Evidence Verification

- **Verifier**: Separate from runtime; does not trust runtime summary.
- **Method**: Rebuild hashes and mandatory-claim coverage from raw events.
- **Failure**: Missing or ambiguous evidence fails closed.
- **Coverage**: ≥ 0.95 of successful P3 executions must have 100% mandatory-claim coverage.

## Evidence Storage

- **Location**: `results/v3/raw/evidence/` directory.
- **Format**: JSONL with SHA-256 hashes.
- **Retention**: Indefinite (frozen).
- **Audit**: All evidence transformations logged.
