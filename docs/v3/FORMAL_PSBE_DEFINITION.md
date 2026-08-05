# Formal definition of Purpose-Selective Bounded Execution

Status: protocol v3 definition  
Applies to: non-TEE confirmatory study unless explicitly extended

## 1. Objects

Let a purpose contract be the immutable tuple

\[
C=(i,p,D,\Pi,W,M,K,R,B,L,E),
\]

where:

- \(i\) is a unique contract identifier and version;
- \(p\) is a specific declared purpose and decision type;
- \(D\) binds the source dataset identity, digest, schema, and row selector;
- \(\Pi\) is a total allow/deny projection over dataset fields;
- \(W\) binds a workload artifact, operation, entry point, and parameters;
- \(M\) binds an exact model artifact or immutable remote model route;
- \(K\) is the capability set: tools, destinations, methods, call/byte limits,
  secret references, and allowed data flow;
- \(R\) is a fail-closed output-release predicate;
- \(B\) is a privacy budget and accountant configuration, or an explicit
  `NOT_APPLICABLE` value;
- \(L\) is lifecycle state, approval separation, effective time, expiry,
  supersession, and revocation;
- \(E\) specifies mandatory evidence claims and hash-chain rules.

Canonical serialization, hash algorithms, and normalization rules are part of
the protocol. A semantically similar but byte-different object is not silently
accepted as the same binding.

An execution request \(q\) names a contract version and supplies input
references, workload parameters, and requested release. An execution trace
\(\tau\) is a sequence of typed events:

\[
\tau=(e_0, e_1, \ldots, e_n),
\]

covering request, approval/lifecycle appraisal, projection, artifact/model
verification, capability decisions, workload execution, privacy reservations
and settlements, release decisions, cleanup, and evidence finalization.

## 2. Acceptance predicate

PSBE-Runtime may start a workload only when all preconditions hold:

\[
\operatorname{Start}(q,C,t) =
\operatorname{CurrentApproved}(C,L,t)
\land \operatorname{Bind}(q,C)
\land \operatorname{VerifyDataset}(D)
\land \operatorname{VerifyProjection}(\Pi)
\land \operatorname{VerifyWorkload}(W)
\land \operatorname{VerifyModel}(M)
\land \operatorname{Reserve}(B).
\]

Every requested effect \(a\) during execution is mediated:

\[
\operatorname{Effect}(a,\tau,C) \Rightarrow
\operatorname{AllowedBy}(a,K,p) \land
\operatorname{AppendEvidence}(a,E).
\]

No output leaves quarantine unless:

\[
\operatorname{Release}(o,\tau,C) =
R(o,\tau,C) \land
\operatorname{PrivacySettled}(B,\tau) \land
\operatorname{EvidenceComplete}(E,\tau).
\]

Missing, stale, ambiguous, unverifiable, or conflicting inputs make these
predicates false. Denial is an observable result and must itself produce
evidence; a denial must not be recoded as successful security if it destroys
authorized availability.

## 3. Purpose selectivity

For an approved-purpose task \(A\), let \(X\) be public/ordinary authorized
features, \(Z\) the confidential attribute authorized by \(C_A\), and \(Y_A\)
the outcome. A useful boundary should allow \(Z\) to improve the expected task
utility:

\[
U_A(f_{C_A}(X,Z),Y_A) > U_A(f_{public}(X),Y_A).
\]

For a distinct task \(B\), \(Z\) is prohibited by \(C_B\), and paired worlds
\((X,Z_0,Y_B)\) and \((X,Z_1,Y_B)\) share identical \(X\) and \(Y_B\). Perfect
purpose non-influence requires equality of output distributions:

\[
f_{C_B}(X,Z_0) \overset{d}{=} f_{C_B}(X,Z_1).
\]

FinBoundBench does not claim to prove this equality for all inputs. It estimates
violations over preregistered paired samples, models, seeds, and attacks. For
deterministic paths it also checks byte-level equality after canonicalizing only
explicitly non-semantic fields.

## 4. Estimands

Let \(U_A(c)\) be the preregistered Task A utility for condition \(c\),
\(U_A(P)\) the public-only baseline, and \(U_A(O)\) the full authorized oracle.
Authorized utility retention is

\[
\operatorname{AUR}(c)=
\frac{U_A(c)-U_A(P)}{U_A(O)-U_A(P)}.
\]

AUR is reported untrimmed with a confidence interval. It is undefined when the
preregistered oracle gain is at or below the task-specific minimum denominator;
that outcome fails the benchmark-sensitivity gate. Values below 0 or above 1
remain visible.

For Task B pair \(j\), let \(d_j(c)=1\) when the released discrete action differs
between confidential variants. Unauthorized Influence Rate is

\[
\operatorname{UIR}(c)=\frac{1}{N}\sum_j d_j(c).
\]

Let \(s_{j0},s_{j1}\in[0,1]\) be normalized released scores and \(l_j\) indicate
any prohibited sentinel or confidential value in a release. Unauthorized
Influence Severity is the conservative bounded maximum

\[
\operatorname{UIS}(c)=\frac{1}{N}\sum_j
\max\{d_j(c), |s_{j0}-s_{j1}|, l_j\}.
\]

UIR, absolute score delta, and disclosure are always reported separately so the
maximum composite cannot hide its cause.

For attack attempt \(k\), classify the result as:

- `PREVENTED`: no prohibited effect and the runtime denied before execution;
- `FAILED_CLOSED`: execution began but no prohibited effect or release occurred;
- `SUCCEEDED_DETECTED`: a prohibited effect occurred but mandatory evidence
  detects it and release is denied;
- `SILENT_COMPROMISE`: a prohibited effect or release occurs and the evidence
  bundle appears valid or omits the violation;
- `INCONCLUSIVE`: instrumentation cannot establish the result.

The silent policy-compromise rate is the fraction of eligible attack attempts
classified `SILENT_COMPROMISE`. Inconclusive attempts remain in the denominator
for a conservative primary analysis and are reported separately.

Evidence coverage is the number of mandatory claims independently reconstructed
from retained artifacts divided by the number required by \(E\). Evidence
verification rate is the fraction of bundles whose signatures/hashes, chain,
bindings, lifecycle, and release decision all verify. Coverage and validity are
not interchangeable.

Availability is successful, policy-conformant completion per authorized
request. Overhead is paired wall time, compute time, provider calls, bytes, and
monetary cost relative to the matched baseline; failed attempts are not dropped
from availability or cost totals.

## 5. Security properties evaluated

1. **Exact binding:** substitutions of purpose, policy, data, projection,
   workload, model, route, or release rule fail closed.
2. **Least data exposure:** the workload receives only \(\Pi(D)\), and denied
   fields cannot re-enter through aliases, encodings, environment, tools, or
   provider payloads.
3. **Complete mediation:** all tools, network calls, secret resolutions, privacy
   spending, and releases pass through the reference monitor.
4. **Lifecycle correctness:** only the current approved version within its time
   window can execute; revocation and supersession are monotonic.
5. **Release confinement:** outputs remain quarantined until native validators,
   privacy settlement, and evidence completion succeed.
6. **Tamper-evident reconstruction:** an independent verifier detects missing,
   reordered, altered, replayed, or cross-run evidence.

The benchmark empirically tests these properties. “Tamper evident” does not mean
that a trusted host cannot suppress all evidence and deny service.

## 6. Threat model

### In scope

- malicious or mistaken API callers;
- prompt injection and adversarial model output;
- compromised or nondeterministic workload code within the declared sandbox;
- field aliasing and common raw/URL/base64/hex encodings;
- unauthorized tools, destinations, methods, calls, and byte volumes;
- stale, revoked, expired, forged, or substituted contract material;
- model/image/workload and remote-route substitution or fallback;
- privacy-budget exhaustion, replay, and reservation/settlement failures;
- output schema, PII, sentinel, cohort, artifact, and approval violations;
- evidence deletion, reordering, tampering, replay, or incomplete binding;
- remote provider failures and route ambiguity.

### Trusted in protocol-v3-psbe-no-tee

- host kernel, container runtime, local administrator, and hardware;
- cryptographic primitives and the independent verifier binary/runtime;
- the correctness of official source-data acquisition after digest verification;
- keys outside the evaluated secret-resolution interface.

### Out of scope for the non-TEE study

- hostile root/kernel/hypervisor, physical access, memory scraping, microcode,
  speculative-execution and other hardware side channels;
- denial of service by the trusted host or evidence-store destruction;
- covert channels not represented by the mediated I/O surface;
- proof of semantic non-use inside an opaque model that legitimately receives a
  field; Task A authorizes use, while Task B relies primarily on non-exposure;
- legal or regulatory compliance conclusions;
- correctness, fairness, or social desirability of real credit decisions.

## 7. TEE extension boundary

A future attested backend replaces part of the trusted-host assumption by
binding the workload/model/runtime measurement and key release to attestation
evidence. It must retain the same contract, attack, release, privacy, and
evidence semantics. TEE and non-TEE results are labeled separately; attestation
does not retroactively strengthen non-TEE claims.
