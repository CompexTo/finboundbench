# Attack Protocol

**Status**: FROZEN (Gate 3, 2026-08-05)

## Attack Families

### 1. Contract/Lifecycle Attacks

- **Description**: Attempts to modify, bypass, or tamper with the purpose contract.
- **Variants**: Contract modification, lifecycle bypass, revocation circumvention.
- **Expected outcome**: Detected and blocked (prevention or fail-closed).

### 2. Workload/Model/Route Attacks

- **Description**: Attempts to substitute workload, model, or route.
- **Variants**: Model substitution, route fallback, workload tampering.
- **Expected outcome**: Detected and blocked (manifest hash mismatch).

### 3. Capability/Data Flow Attacks

- **Description**: Attempts to bypass capability restrictions or data flow controls.
- **Variants**: Unauthorized capability, data exfiltration, projection bypass.
- **Expected outcome**: Detected and blocked (capability enforcement).

### 4. Release Attacks

- **Description**: Attempts to bypass the release mechanism.
- **Variants**: Release predicate bypass, quarantine escape, output tampering.
- **Expected outcome**: Detected and blocked (release enforcement).

### 5. Privacy Attacks

- **Description**: Attempts to exhaust the privacy budget or extract private information.
- **Variants**: Budget exhaustion, membership inference, score leakage.
- **Expected outcome**: Detected and blocked (budget enforcement).

### 6. Evidence Attacks

- **Description**: Attempts to tamper with or forge the evidence bundle.
- **Variants**: Evidence omission, hash forgery, claim fabrication.
- **Expected outcome**: Detected and blocked (evidence verification).

## Attack Execution

- **Registration**: All attacks pre-registered in `ATTACK_PROTOCOL.md`.
- **Seeding**: Random seed for attack variant selection frozen.
- **Isolation**: Each attack variant executed independently.
- **Budget**: Attacks consume budget like normal invocations.
- **Documentation**: All attack outcomes recorded in raw events.

## Attack Outcomes

| Outcome | Description |
|---------|-------------|
| **Prevented** | Attack detected and blocked before execution. |
| **Fail-closed** | Attack detected and blocked during execution. |
| **Detected success** | Attack succeeded but was detected post-execution. |
| **Silent compromise** | Attack succeeded and was not detected. |
| **Inconclusive** | Attack outcome cannot be determined. |

## Attack Metrics

- **Prevention rate**: Fraction of attacks prevented.
- **Fail-closed rate**: Fraction of attacks failing closed.
- **Silent compromise rate**: Fraction of attacks succeeding silently.
- **Detection rate**: Fraction of attacks detected (prevented + fail-closed + detected success).

## Attack Budget

- **Registered attacks**: 6 families × 5 variants = 30 attack invocations.
- **Cost per attack**: €0.04 (conservative estimate).
- **Total attack cost**: €1.20.
- **Contingency**: €5.00 for repeated attacks.
