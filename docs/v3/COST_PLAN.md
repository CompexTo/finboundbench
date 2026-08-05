# Cost and execution-authorization plan

Status: no paid authorization recorded for protocol v3  
Currency: EUR ledger; provider USD charges converted with a recorded rate and
timestamp only after authorization

## Principles

1. No API key value, key hash, or recoverable derivative may enter Git, prompts,
   event evidence, logs, or paper artifacts.
2. A provider secret may be read only from an ignored environment/secret store
   through the reviewed secret-reference path.
3. Every paid phase requires a numeric category cap and absolute global cap
   recorded before the first request.
4. Reservations precede calls; settlements record actual charge or a
   conservative maximum for failures. Ledger reconciliation is a gate.
5. No automatic fallback and no confirmatory automatic retry.
6. Prices and model availability are time-varying. They are captured from the
   provider at admission time, not guessed in this protocol.

## Phase gates

| Phase | Scope | Expected provider cost | Authorization |
| --- | --- | ---: | --- |
| N0 | unit/property tests, deterministic reference models, test doubles, evidence tampering, local Docker | EUR 0 | authorized by the request |
| N1 | complete no-cost protocol dry run with 20 development pairs and reduced bootstrap repetitions | EUR 0 | authorized by the request |
| L0 | full local open-weight factorial if three exact local models are available | EUR 0 provider fees; local compute reported | allowed after N1 freeze |
| R0 | one schema/route/no-fallback smoke call per candidate commercial model | unset | blocked pending API key and explicit numeric cap |
| R1 | position/batch diagnostic for models passing R0 | unset | blocked pending R0 reconciliation and phase cap |
| R2 | confirmatory commercial model matrix | unset | blocked pending R1 freeze, power/sample freeze, and phase cap |
| T0 | AWS/TEE design or execution | unset | prohibited until all non-TEE results freeze and separate AWS authorization is recorded |

## Call-volume envelope

The upper-bound confirmatory inference design contains:

- 2 datasets × 2 tasks × 7 inference conditions;
- 100 pairs/dataset, 2 variants/pair;
- 3 models × 3 repetitions.

At a fixed batch of 40 records, this is
\(2\times2\times7\times5\times3\times3=1{,}260\) inference calls before
diagnostics or attack-specific model calls. This is an upper bound, not a
purchase commitment. Local execution should cover the factorial; commercial
replication may use a preregistered subset only if the subset is frozen before
commercial outcomes and the paper labels the scope.

At admission time, the cost estimator computes per model:

\[
\text{max cost} =
N_{calls}(T_{in}^{max}P_{in}+T_{out}^{max}P_{out}) + \text{fixed fees},
\]

using provider-published unit prices, maximum registered tokens, taxes/fees
where known, and a 20% conservative contingency. Actual and conservative
settlements are both retained.

## Paid-readiness checklist

The project is ready to request `OPENROUTER_API_KEY` only when all are true:

- protocol, hypotheses, sample IDs, prompts, schemas, models-under-consideration,
  batch size, ordering, stop rules, and analysis code are frozen;
- the complete N1 dry run passes from clean input through regenerated paper
  assets and independent evidence verification;
- secret scans and provider adapter tests pass;
- v3 uses an append-only budget ledger with reservation, settlement, rollback,
  and reconciliation tests;
- a current provider model/price/route manifest has been reviewed;
- a human supplies the numeric EUR cap and authorizes the specific paid phase.

Until then, no key is requested. Supplying a key does not by itself authorize an
uncapped run.

## Failure charging

HTTP errors, timeouts, malformed outputs, and provider-route failures are
charged at the provider-reported amount when available. When actual usage is
unknown, the reservation's conservative maximum remains committed. A later
verified invoice/usage record may reconcile it through a new append-only event;
history is not edited.

## Compute and environmental reporting

Provider price is not the only overhead. Local and TEE phases report hardware,
wall/CPU/GPU time, peak memory where available, image size, input/output bytes,
and energy telemetry if measured reliably. No carbon or energy claim is made
from hardware time alone.
