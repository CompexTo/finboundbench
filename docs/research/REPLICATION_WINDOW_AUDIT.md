# Replication Window Audit — Protocol V4 Purposebinding

**Scope:** selection and acceptance of `replication-window-8` (Kimi K3 /
`fraud_review`) after seven earlier windows were not admitted.
**Auditor:** independent release-engineering pass (2026-08-09), re-deriving
all window facts from frozen outcome records and raw event files.
**Conclusion:** the acceptance of window 8 follows the preregistered
provider-failure handling and execution-window rules; no evidence of
outcome-dependent selection; the earlier windows are unusable for inference
by construction, and that is disclosed here rather than hidden.

---

## 1. What happened, window by window

| Window | Persisted events | Outcome | Failure pattern | Verdict |
|---|---|---|---|---|
| 1 | 1,560 (1,349 KB) | 512 ok / 1,048 failed | Provider transport failures, time-blocked: ND ok=1/360, A3 ok=0/240, P0 ok=50/240 | NOT ADMITTED (provider) |
| 2 | 1,560 (1,520 KB) | 835 ok / 725 failed | Provider transport failures, time-blocked: ND ok=0/360, P3 ok=0/240 | NOT ADMITTED (provider) |
| 3–5 | none | no events persisted | Sessions aborted before any persisted inference | NOT ADMITTED (no data) |
| 6 | 120 | 113 ok / 7 failed | **Operational deviation:** conditions passed to the CLI as one comma-joined token `A0,A1,A3,P0,P3,ND`; every event carries that bogus condition; per outcome file: "no registered condition; no inferential weight; events retained only as diagnostic route evidence" | NOT ADMITTED (protocol deviation) |
| 7 | 1,560 | 170 ok / 1,390 failed | 1,023 HTTP 403 (hard denial), 351 transport, 16 rate-limit; all failures on route `morph`; contiguous fail-run of 1,374 events | NOT ADMITTED (provider; route unavailable) |
| **8** | **1,560** | **1,544 ok / 16 failed (99.0%)** | 14 `PROVIDER_TRANSPORT_ERROR`, 2 `PROVIDER_TIMEOUT`; `auth_refusal_absent: true`; transient only | **ADMITTED** (`RUN_COMPLETE_99PCT_SUCCESS`, accepted with registered failure handling) |

Window 8 admission record (`replication-window-8-outcome.json`):

- `decision_point`: "data is analyzable with standard failure handling;
  runner-level eligibility FAIL is due to provider_success < 1.0 gate"
- recorded 2026-08-07T07:00:00Z, **before** any statistical analysis of the
  window (statistics were computed from the frozen event stream afterwards)
- per-condition complete pairs: A0=119, A1=120, A3=118, P0=113, P3=120, ND=120;
  114 pairs complete on all six conditions

## 2. Were the rules preregistered?

Yes, all relevant rules predate window 8 and were locked at the confirmatory
freeze (2026-08-07):

1. **`docs/v4/PROVIDER_FAILURE_TAXONOMY.md`** — a provider failure is never a
   behavioral observation; a decision-change requires two valid outputs;
   paired analyses use pairs with both outputs valid (per-condition n
   reported); no failure is ever deleted. Registered before the confirmatory
   windows ran.
2. **`docs/v4/CONFIRMATORY_ROUTE_POLICY.md` §3.4 (execution-window rule)** —
   each study runs in a single tightest calendar session; a study is not
   resumed across a break without registering a new execution window. This is
   exactly why windows 1–8 each exist as separate registered windows.
3. **Route policy §3.2** — pinned route unavailable or metadata change
   mid-study → STOP, freeze partial results, never swap routes within a
   study. Window 7's 403 wall on route `morph` is the canonical instance.
4. **Route policy §3.3** — "Partial data cannot confirm. A partial primary may
   be reported descriptively but cannot support a 'confirmed' reading unless
   the preregistered N is reached." This bars using windows 1–2 as a
   substitute sample.

## 3. Was any result information involved in choosing window 8?

No. The admission decision (07:00Z) records only operational statistics —
event counts, provider-success rate, failure classes — and explicitly checks
`auth_refusal_absent`. No metric (BACC, UIR, ND floor) is computed or
referenced at decision time, and the statistical reports were generated after
the window was frozen. The failures classified as transient were not
behavioral observations, so no partial behavioral signal existed to select on.

## 4. Are the exclusions registered before behavioral outcomes?

Yes — the taxonomy (failures never behavioral; pair-validity rule) is a
registered protocol document; the exclusion criteria are stated in the
outcome files before any analysis. The 16 excluded window-8 events are
preserved in the raw event stream (nothing is deleted), and the verification
bundle (`results/v4/evidence/confirmatory-verification-bundle.json`) and
independent statistics cross-check
(`results/v4/evidence/independent-stats-crosscheck.json`) recompute all
numbers from the raw events with the same exclusion rule.

## 5. Sensitivity: why no pooled multi-window analysis is meaningful

The audit instruction asks for a sensitivity analysis including all usable
windows *where statistically meaningful*. We checked the missingness pattern
in the raw events and it is **not** ignorable for windows 1–2:

- window 1: ok events are confined to early-session conditions (A0 ok=240/240,
  A1 ok=207/240) while ND ok=1/360 and A3 ok=0/240 — the failure is
  time-correlated with the condition scheduling order, so the ok subset is a
  biased, condition-blocked sample;
- window 2: ND ok=0/360, P3 ok=0/240 — the two conditions needed for the
  floor-relative comparisons are entirely missing;
- window 7: only A0 has ok events (170/240).

No paired ND/floor or P0/P3 comparison can be formed from those subsets, so a
pooled sensitivity analysis would produce estimates with no registered
estimand, severe selection bias, and zero statistical meaning. The honest
treatment — documented here — is:

1. windows 1–2, 6–7 are excluded per the preregistered rules (provider
   failure; protocol deviation; route unavailability);
2. window 8 is the only window reaching preregistered N under the registered
   task conditions;
3. the exclusion is outcome-independent and disclosed in full.

## 6. Registered caveats carried into the paper

- The replication study required 7 non-admitted windows before window 8;
  provider availability is a documented, model-agnostic confounder in this
  benchmark family.
- Window-8 provider success is 99.0%, not 100%; the 16 excluded events are
  transient transport/timeout failures, none are policy or behavioral events.
- A model whose provider is operationally unstable cannot be evaluated on this
  protocol without repeated windows (operational cost is disclosed in
  `docs/v4/COST_PLAN.md` and `results/v4/performance/`).

## 7. Audit verdict

| Question | Answer |
|---|---|
| Why did windows 1–7 fail? | Provider/infrastructure failures (1,2,7), aborted sessions (3–5), one CLI-format deviation (6) |
| Outcome-dependent failures? | No — all classes are transport/HTTP/format; none are behavioral |
| Did any result information influence window choice? | No — admission used operational statistics only, recorded before analysis |
| Did window 8 acceptance follow a preregistered rule? | Yes — registered failure taxonomy + execution-window rule; `ACCEPTED_WITH_REGISTERED_FAILURE_HANDLING` |
| Were exclusions registered before behavioral outcomes? | Yes |
| Pooled sensitivity meaningful? | No — condition-blocked missingness in 1–2; documented above |
