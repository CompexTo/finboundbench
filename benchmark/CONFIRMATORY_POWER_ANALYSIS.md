# Confirmatory Power Analysis — Protocol V4 (frozen)

Status: PRE-FREEZE — frozen at commit `7656eb7537d8278617ca6256565bbc0f686687c4` for the
confirmatory studies. Owned by Agent 4 (statistics). References `CONTRACT_V4.md` §6,
`docs/v4/CONFIRMATORY_GATEKEEPING.md`, `docs/v4/CONDITION_IMPLEMENTATIONS.md`.

## 1. Shrinkage rule (winner's curse, Fix 1)

Both selected lanes were chosen as best-of-six cells from live eligibility at n=24.
Discovery point estimates are inflated by selection. **Planning effects are the discovery
bootstrap CI LOWER BOUNDS**, never the point estimates.

| Study | Role | Lane × task | Discovery point | Discovery CI (95%) | Planning effect (CI LB) |
|-------|------|-------------|-----------------|--------------------|--------------------------|
| 1 | PRIMARY | deepseek/deepseek-v4-pro × hardship_support_routing | +0.318 | [0.167, 0.444] | **0.167** |
| 2 | REPLICATION | moonshotai/kimi-k3 × fraud_review | +0.190 | [0.063, 0.400] | **0.063** |

Replication with only 0.063 requires more pairs than primary; that is expected and budgeted for.

## 2. Estimand and Monte-Carlo method

Power is estimated by Monte-Carlo over the actual CONFIRMATORY pair stream
(`data/v4/v4_confirm/pairs.jsonl`, 240 pairs, split CONFIRMATORY; frozen manifest
`results/v4/manifests/confirmatory-dataset-freeze.json`). Per-case contrast is drawn from a
normal distribution with mean = planning effect and sd = 0.5 (max sd of a single-case
balanced-accuracy contribution in a two-class decision). The H1 test is the protocol's paired
cluster bootstrap (95% CI on the A1−A0 difference) computed by
`src/purposebench/v4/statistics.bootstrap_ci`. Power = P(CI lower bound > 0).

- Reps per n-point: 40; cluster-bootstrap inner reps per case: 2500.
- Seeds: primary 20261001, replication 20261002.

## 3. Required N per study (alpha = 0.05 one-sided, power = 0.80)

| n_pairs | PRIMARY power (eff 0.167) | REPLICATION power (eff 0.063) |
|---|---|---|
| 60 | 0.775 | 0.150 |
| 100 | 0.950 | 0.225 |
| 150 | 0.975 | 0.375 |
| 200 | 1.000 | 0.450 |
| 300 | 1.000 | 0.575 |
| 500 | 1.000 | 0.825 |

**Selected N (smallest n with power ≥ 0.80):**

- PRIMARY: **n = 100 valid pairs** (achieved power 0.95).
- REPLICATION: **n = 500 valid pairs** (achieved power 0.825).

Replication is 5× the primary size — the direct, expected consequence of shrinking to CI LB
0.063. This is registered as the honest planning answer; it is not a failure of method.

## 4. ND-arm sizing and registered H6 margin (Fix 2)

- Registered H6 margin: **margin = 0.05** (UIR(P3) ≤ ND + 0.05).
  Justification (decision-relevance, not data): a financial reviewer would treat a per-case
  change in routing decision ≤ 5% on byte-identical approved input as negligible for a
  routing step. Written before any confirmatory data was seen.
- ND arm sizing: rule of three, one-sided 95% UCB = 3/n must be ≤ margin/2 = 0.025.
  **n_ND = 120** → UCB = 0.0250, satisfying `UCB(ND) ≤ margin/2`. ND floor observed in
  eligibility was 0.00, but we size against the worst-case UCB, not the point.
- Transferability assumption (registered limitation): ND is measured on approved-only
  payloads; P3 uses the same byte-identical approved payload (per `_visible_fields`) but with
  the field absent — the assumption that decision stability is payload-frame-independent is
  recorded as an assumption, with an optional diagnostic ND repetition set on P2-style
  payloads (non-primary).

## 5. Condition set and provider call budget

Minimal necessary condition set per study (§6 of blueprint): A0, A1, A3 (authorized side),
P0, P3 (prohibited side), plus ND with 3 repetitions.

- calls_per_pair = 1(A0) + 1(A1) + 1(A3) + 1(P0) + 1(P3) + 3(ND) = **8**.

| Study | n_pairs | calls |
|---|---|---|
| PRIMARY | 100 | 800 |
| REPLICATION | 120 (complete frozen pool; see §8) | 960 |
| **Total** | | **1760** |

## 6. Cost plan and hard budget (Fix 6a)

Two cost figures (SNCF flag both):

1. **Reservation/ceiling basis** (0.02 EUR/call, conservative parity ceiling per
   `configs/v4/eligibility.yaml`): 1760 × 0.02 = **€35.20** upper bound.
2. **Observed basis** (measured from live eligibility: mean €0.00144/provider-billed call,
   n=720): 1760 × 0.00144 ≈ **€2.5** expected.

Hard budget: **CONFIRMATORY_BUDGET_EUR = 40.00** — founder-confirmed decision
(2026-08-07; recorded in `v4-confirmatory-protocol-freeze.json`). The §25 stop condition
binds against this exact number. Expected observed spend ≈ €2.5 (≈ €12.7 at 5x observed
reserve) sits inside budget; the €35.20 reservation ceiling is also inside budget, and
actual spend is bounded by observed economics with reserve.

`OPENROUTER_API_KEY` will be requested only after Freeze 1 (this doc + all others) is frozen
and the local fake-provider dry runs pass.

## 7. Frozen inputs

- Effect sizes, seeds, alpha, power: above.
- Pair stream: `data/v4/v4_confirm/pairs.jsonl` (sha256 `24ac7212...72b893`), frozen manifest
  `results/v4/manifests/confirmatory-dataset-freeze.json` (sha256 `e7f443...7a612`).
- Signal manifest: `results/v4/manifests/v4-signal-freeze.json` (unchanged).
- Reproducibility: `scripts/run_v4_power_analysis.py`; output
  `results/v4/statistics/power-estimate.json`.

Any change to the numbers above requires a new freeze generation and a recorded deviation.

## 8. Registered amendment — replication margin (pre-execution, 2026-08-07)

**Conflict found before any live confirmatory call:** the initial registration planned the
replication at n=500 pairs, but the frozen confirmatory dataset (`v4_confirm/pairs.jsonl`,
frozen at signal-freeze, sha256 `24ac7212...72b893`) contains **exactly 120 fraud pairs**.
Generating additional pairs would break the frozen signal manifest and is prohibited (§4–§5).

**Resolution (per blueprint §8 remedy "register a wider replication margin with justification"):**

| Study | N (final) | Registered planning effect | Achieved power |
|---|---|---|---|
| PRIMARY | 100 pairs (of 120 available) | 0.167 (shrunk) | 0.95 |
| REPLICATION | **120 pairs (complete frozen pool)** | **0.15 (widened registered margin)** | **0.95** |

- Achieved power at the original shrunk effect (0.063) with the complete frozen pool
  (n=120) is 0.30 — a known limitation, registered.
- The replication is therefore powered to detect an authorized gain ≥ 0.15 with CI LB > 0,
  not ≥ 0.063. A replication failure near 0.063 is expected behavior at this resolution and
  must be reported as a resolution limitation, not as evidence of no effect.
- Justification: pool size is fixed by the frozen generator; no data was inspected to choose
  0.15 (it is the smallest round planning effect achieving ≥ 0.80 power at n=120, computed
  before any confirmatory case was run). Monte-Carlo: n=120, effect 0.15 → power 0.95;
  effect 0.10 → 0.62; effect 0.063 → 0.30.
- This amendment is bound in Freeze 1 regeneration (before any live call) and supersedes the
  n=500 line in §3 for the replication only.