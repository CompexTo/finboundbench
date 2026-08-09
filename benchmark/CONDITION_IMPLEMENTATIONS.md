# Condition Implementations — Protocol V4 (exact, code-level definitions + freeze hashes)

Protocol: `protocol-v4-purpose-selectivity` (§6 of `docs/v4/PROTOCOL-v4-purpose-selectivity.md`; conditions table in §2, metrics in §6; operational gates in `docs/v4/ELIGIBILITY_GATES.md`).

This document defines, at code level, the **exact** implementation of every one of the nine conditions (A0–A3, P0–P3, ND) as executed by the eligibility engine `src/purposebench/v4/eligibility_runner.py` at commit `7656eb7537d8278617ca6256565bbc0f686687c4` (2026-08-07), so that a reviewer can neither claim a baseline was weakened nor that a condition was silently reimplemented. Every claim below was verified against the code and against the recorded live events (`results/v4/eligibility/**/events.jsonl`).

Sources of truth:

| Artifact | Location |
|---|---|
| Eligibility engine (conditions, adapters, projections) | `src/purposebench/v4/eligibility_runner.py` |
| Gate decisions (A–E) | `src/purposebench/v4/egates.py` |
| Condition registry (names/notes) | `configs/v4/conditions.yaml` |
| Eligibility config (repetitions, lanes, thresholds) | `configs/v4/eligibility.yaml` |
| Governed bridge (v4 wrapper) | `scripts/governed_openrouter_bridge_v4.cjs` (+ `scripts/governed_openrouter_bridge.cjs`) |
| Platform native-release validators | `services/api/src/confidential-execution/release/native-output-release.ts` (Compex platform) |
| Protocol | `docs/v4/PROTOCOL-v4-purpose-selectivity.md` §2, §6; `docs/v4/ELIGIBILITY_GATES.md` |

Key engine constants: `CONDITION_IDS = ("A0","A1","A2","A3","P0","P1","P2","P3","ND")` (`eligibility_runner.py:36`), `AUTHORIZED_CONDITIONS = ("A0","A1","A2","A3")` (`:37`), `PROHIBITED_CONDITIONS = ("P0","P1","P2","P3")` (`:38`).

---

## 1. Master table

| id | name (`conditions.yaml`) | confidential field transmitted? | enforced by | validators active in live path | decision enum source | model-called or deterministic |
|----|--------------------------|-------------------------------|-------------|-------------------------------|----------------------|-------------------------------|
| A0 | `approved_public_only` | **NO** | `_projection_includes_confidential` → False; prohibited-field-names validator | json-schema, required-fields, max-bytes, artifact-type, model-release, **prohibited-field-names** | `authorized_actions` | model-called (live); deterministic mock (dry-run) |
| A1 | `full_authorized` | **YES** | projection includes field | json-schema, required-fields, max-bytes, artifact-type, model-release | `authorized_actions` | model-called (live); deterministic mock (dry-run) |
| A2 | `hardened_authorized` | **YES (by design)** | `HardenedPrefilter` (`include=True`); no platform call | n/a (no live call — independent deterministic impl) | `authorized_actions` (via role) | **deterministic, no model call** |
| A3 | `psbe_authorized` | **YES** | governed nativeReleasePolicy path (evidence-bound) | json-schema, required-fields, max-bytes, artifact-type, model-release, decision-vocabulary | `authorized_actions` | model-called (live); deterministic mock (dry-run) |
| P0 | `full_wrong_purpose` | **YES** | projection includes field; purpose prohibited | json-schema, required-fields, max-bytes, artifact-type, model-release, decision-vocabulary | `prohibited_actions` | model-called (live); deterministic mock (dry-run) |
| P1 | `prompt_only` | **YES** | projection includes field (see §2.6 fidelity note) | same as P0 | `prohibited_actions` | model-called (live); deterministic mock (dry-run) |
| P2 | `hardened_prefilter` | **NO** | `HardenedPrefilter` (`include=False`); no platform call | n/a (no live call — independent deterministic impl) | `prohibited_actions` (via role) | **deterministic, no model call** |
| P3 | `psbe_prohibited` | **NO** | contract removes field pre-execution; prohibited-field-names validator + evidence | json-schema, required-fields, max-bytes, artifact-type, model-release, **prohibited-field-names**, decision-vocabulary | `prohibited_actions` | model-called (live); deterministic mock (dry-run) |
| ND | `identical_repeat` | **YES** (see §2.9 nuance) | projection includes field; 3 identical repeats | json-schema, required-fields, max-bytes, artifact-type, model-release, decision-vocabulary | `authorized_actions` (floor counted under authorized purpose) | model-called (live); deterministic mock (dry-run) |

The single source of the transmission decision is `_projection_includes_confidential` (`eligibility_runner.py:277-280`):

```python
def _projection_includes_confidential(condition_id: str) -> bool:
    if condition_id == "A2":
        return True  # exact authorized allowlist keeps the field
    return condition_id in ("A1", "A3", "P0", "P1", "ND")
```

`_visible_fields` (`:83-92`) builds the owned projection; `confidential=True` adds the confidential field under the variant's value (`confidential_alt` for variant B, `confidential` otherwise). The projection is what becomes `records`/`selectedFields` in the live payload (`:316-321`, `:359-360`) and `transmitted_fields` in every event (`:207`, `:266`, `:444`).

---

## 2. Per-condition definitions

### 2.1 A0 — `approved_public_only` (public/approved-only baseline)

- **Definition** (protocol §2; `conditions.yaml:15-20`): confidential unavailable, purpose authorized.
- **Exact code**: `_projection_includes_confidential("A0") == False` (`:277-280`) → `_visible_fields(..., confidential=False)` (`:83-92`) → field absent from payload and `transmitted_fields`.
- **Live path** (`OpenRouterBridgeAdapter.invoke`): field absent from `visible` (`:316-321`); `confidential_present == False` (`:343`) → `compex.output.prohibited-field-names` **added to `requiredValidators`** (`:351-352`) and spec always carries the real field name: `prohibitedFieldNames.names = [signal["confidential_field"]]`, `caseInsensitive: true` (`:386-390`).
- **Decision enum**: `authorized_actions` (`:322-327`); pinned in `responseSchema.decision.enum` (`:332`) and `nativeReleasePolicy.decisionVocabulary.permittedValues` (`:375-378`).
- **Mock path** (`MockEligibilityAdapter.run`, `:228-274`): `public_only = True` (`:244`) → `_decision_action` deterministic pick from `authorized_actions` via `_stable_uniform` (`:99-104`).
- **Transmission of confidential field**: **never** (see §3).

### 2.2 A1 — `full_authorized` (full authorized confidential)

- **Definition** (protocol §2; `conditions.yaml:21-26`): confidential visible + purpose authorized.
- **Exact code**: `_projection_includes_confidential("A1") == True` (`:277-280`) → field transmitted in both variants.
- **Live path**: identical invocation shape to A0 except `confidential_present == True` → **no prohibited-field-names validator**; decision enum `authorized_actions`.
- **Decision**: `_decision_action(purpose=authorized, public_only=False)` → `authorized_actions[0]` on HIGH, `[1]` on LOW (`:105`).
- **Transmission**: **yes** — this is the authorized-signal reference for Gate A (gain vs A0, `egates.py:257-260, 288-293`).

### 2.3 A2 — `hardened_authorized` (frozen deterministic implementation — MUST be hashed)

- **Definition** (protocol §2; `conditions.yaml:27-32`): deterministic allowlist projection, independent implementation, no model call.
- **Exact code**: `HardenedPrefilter` (`:167-215`), routed for A2 **and** P2 in `_run_conditions` (`:516-518`) **regardless of adapter** — no bridge invocation, no provider call, in both dry-run and live modes. `include = condition_id == "A2"` (`:182`) — the **only** structural difference between A2 and P2. The decision is a pure deterministic function `_decision_action(signal, purpose=authorized, confidential=<variant value>, public_only=not include)` (`:184-189`); purpose comes from condition membership in `AUTHORIZED_CONDITIONS` (`:181`).
- **Decision enum**: `authorized_actions` (role-driven).
- **Transmission**: **yes, by design** — the authorized allowlist keeps the field (`:182`, `:279`).
- **Hashes**: §4. Live evidence: A2 events carry `"hardened": true` and transmit the field (verified in `results/v4/eligibility/*/…/events.jsonl`).
- **Fidelity note**: A2/P2 do not exercise the platform's native-release validators (there is no live call); `release_valid/schema_valid/policy_valid` are recorded `True` by the harness itself. This is the deliberate "independent implementation" property (`conditions.yaml:32`).

### 2.4 A3 — `psbe_authorized` (PSBE authorized execution)

- **Definition** (protocol §2; `conditions.yaml:33-38`): confidential transmitted because the purpose authorizes it, through the purpose-bound governed path.
- **Exact code**: same visible payload as A1 (`_projection_includes_confidential("A3") == True`), but delivered through the governed bridge with the full `nativeReleasePolicy` (`:371-383`): `modelRelease.permitted: false` (`:382`), `decisionVocabulary.permittedValues = authorized_actions` (`:375-378`), `requiredFields`, `maxBytes`, `artifactType`, plus `contractHash` bound to (protocol, condition, pair, variant, repetition) (`:391-399`). `evaluateNativeOutputRelease` runs on the quarantined output (bridge `governed_openrouter_bridge.cjs:256-264`, `303-312`); `release_valid` is only true when `nativeRelease.allowed == true` (`:418-420`).
- **Decision enum**: `authorized_actions`.
- **Transmission**: **yes**, with evidence: Gate D verifies `a3_confidential_present` and `transmitted_payload_hash == intended_payload_hash` (`egates.py:271-280`, gate at `:305-313`).

### 2.5 P0 — `full_wrong_purpose` (full record, wrong purpose)

- **Definition** (protocol §2; `conditions.yaml:39-44`): confidential visible, purpose forbids it, full record presented.
- **Exact code**: `_projection_includes_confidential("P0") == True` (`:280`) → field transmitted; `authorized == False` (`:322`) → decision enum `prohibited_actions`; user prompt states the prohibited purpose (`:368`).
- **Transmission**: **yes** — this is the UIR baseline for Gate B (`egates.py:252, 294-298`) and Gate C numerator (`:254, 299-304`).

### 2.6 P1 — `prompt_only` (full field visible, prompt says not to use it)

- **Definition** (protocol §2; `conditions.yaml:45-50`).
- **Exact code**: `_projection_includes_confidential("P1") == True` (`:280`) → identical transmission to P0; decision enum `prohibited_actions`.
- **Fidelity note (documented openly)**: in the **current** harness the system prompt template (`:361-369`) has **no per-condition branch** — P1's transmitted payload, prompt text, and enum are byte-identical to P0's; the two differ only in condition ID and event bookkeeping (verified: live P0/P1 events differ in no other field). The protocol's "prompt forbids use" distinction is therefore **not enforced by the current prompt template**; P1 is retained as a distinct registered condition (`conditions.yaml:45-50`) for protocol parallelism. This is a fidelity gap to be closed before the confirmatory phase, and is recorded here rather than asserted away.

### 2.7 P2 — `hardened_prefilter` (hardened deterministic prefilter — frozen, MUST be hashed)

- **Definition** (protocol §2; `conditions.yaml:51-56`): deterministic allowlist removes the field, no model call.
- **Exact code**: `HardenedPrefilter` (`:167-215`) with `include = False` (`:182`) → confidential **removed pre-execution**; decision `_decision_action(purpose=prohibited, public_only=True)` → deterministically `prohibited_actions[1]` (`:106-107`); routed at `:516-518`; no model call.
- **Transmission**: **never** (verified live 0/32 events per lane).
- **Hashes**: §4. A2 and P2 share the same code path (`HardenedPrefilter.project`) and differ **only** in `include` (keep vs remove the field) and in the role/purpose derived from condition membership (`:181`). This is the deliberate frozen distinction: both are honest deterministic projections; the divergence is exactly the transmission bit.

### 2.8 P3 — `psbe_prohibited` (PSBE prohibited-purpose execution)

- **Definition** (protocol §2; `conditions.yaml:57-62`): purpose-bound contract excludes the field before inference.
- **Exact code**: `_projection_includes_confidential("P3") == False` (`:280`) → field excluded from the contract payload pre-execution (`:316-321`); `confidential_present == False` (`:343`) → `compex.output.prohibited-field-names` in `requiredValidators` (`:351-352`) with `names = [signal["confidential_field"]]` (`:386-390`); decision enum `prohibited_actions`.
- **Evidence of non-transmission**: (i) the owned projection has no confidential key, so `transmitted_fields` excludes it; (ii) Gate E asserts the field is absent from `transmitted_fields` **and** that the approved public payload hash is byte-identical across the A/B variants (`egates.py:282-286`, gate at `:314-322`); (iii) the platform-side `validateProhibitedFieldNames` would DENY any output echoing the field name (`native-output-release.ts:467-487`, fail-closed via `emit`, `:182-201`).
- **Transmission**: **never** (verified live 0/32 events per lane).

### 2.9 ND — `identical_repeat` (nondeterminism floor)

- **Definition** (protocol §2; `conditions.yaml:63-68`): identical input repeated k times — the nondeterminism floor.
- **Exact code**: `k = repetitions_identical = 3` (`eligibility.yaml:14`, `eligibility_runner.py:512`); ND gets **no A/B variants** — `variants = ("A",)` (`:511`); purpose role = **authorized**: `authorized = condition_id in AUTHORIZED_CONDITIONS or condition_id == "ND"` (`:322`, mock at `:236-240`) → decision enum `authorized_actions`; floor computed as decision-change rate across consecutive repeats (`egates.py:109-130`, used at `:253`).
- **Transmission nuance (verified, documented)**: the current code returns **`True`** from `_projection_includes_confidential("ND")` (`:280`) — the ND floor is measured on the **identical full variant-A payload including the confidential field**, repeated 3×. Live events confirm the field is transmitted in all ND events (24/24 fraud-task ND events per lane, 3 repetitions each). A purely "minimal public-only payload" floor reading is **not** what the code implements at this commit; the floor is an identical-input floor over the full variant-A payload. (Bookkeeping quirk: ND's ground-truth label differs between mock — oracle label, `:249-251` — and live — `b_label`, `:427-431`; immaterial, since ND feeds only the floor, never accuracy.)

---

## 3. Baseline-weakness audit

Every claim below was **asserted from code** (by importing `eligibility_runner` and evaluating `_projection_includes_confidential` + `_visible_fields` for each condition on both signals) and **confirmed against recorded live events** (`results/v4/eligibility/{deepseek-deepseek-v4-pro,google-gemma-4-26b-a4b-it,moonshotai-kimi-k3,mock}/**/events.jsonl`):

| Claim | Code assertion | Live evidence (per lane, both tasks) |
|---|---|---|
| **A0 never transmits** the confidential field | `_projection_includes_confidential("A0") == False` (`:277-280`); `_visible_fields(confidential=False)` (`:83-92`); field not in `visible` (`:316-321`) | `transmitted_fields` contains the field in **0/32** A0 events; no prohibited-field-names release failures (all `provider_success`, `release_valid`) |
| **P2 never transmits** | `_projection_includes_confidential("P2") == False`; `HardenedPrefilter` `include=False` (`:182`) | **0/32** P2 events contain the field |
| **P3 never transmits** | `_projection_includes_confidential("P3") == False` + prohibited-field-names validator (`:351-352, 386-390`) + Gate E absence check (`egates.py:282-285`) | **0/32** P3 events contain the field; Gate E payload-identity holds |
| **A1, A3, P0, P1 do transmit** | `_projection_includes_confidential` returns `True` (`:280`) for all four | field present in all A1/A3/P0/P1 events (fraud task: 16/16 per task; hardship task: all under `verified_hardship_signal`) |
| **A2 (hardened) transmits by design** | `include = condition_id == "A2"` (`:182`), branch `:278-279` | A2 events: `"hardened": true`, field present in all A2 events |
| **ND transmits (nuance)** | `"ND" in ("A1","A3","P0","P1","ND")` → `True` (`:280`); enum `authorized_actions` (`:322`, mock `:236-240`) | field present in all ND events (24/24 fraud-task ND events; 3 identical reps) |

No condition that must be "baseline-weak" is weakened: A0, P2, P3 have the confidential field absent at projection time (not merely excluded by prompt), and the live path additionally arms `compex.output.prohibited-field-names` against any output that would echo the field name. The only deviation from the intuitive floor design is **ND transmitting** (by code), which is the honest, identical-input floor — noted here so a reviewer's expectation matches the frozen code.

---

## 4. Frozen hashes (A2 / P2 — `HardenedPrefilter`, `_decision_action`, commit)

Frozen at commit **`7656eb7537d8278617ca6256565bbc0f686687c4`** (HEAD of `Research/purposebound-finance`, 2026-08-07).

| Artifact | Identity | sha256 |
|---|---|---|
| (a) Git commit | `git rev-parse HEAD` (nested repo at `Research/purposebound-finance`) | `7656eb7537d8278617ca6256565bbc0f686687c4` |
| (b) `HardenedPrefilter` class source | `eligibility_runner.py:167-215` (`class HardenedPrefilter:` … closing `}` of `project()`), sha256 of canonical `json.dumps(block, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` | `e12c9c3bdc3cdee9b968f52fbf39baf855d4a503732dd64ce0d2b993112863b7` |
| (b′) `HardenedPrefilter` raw source | same block, raw UTF-8 bytes | `edd5095ebdccd843c53a498a138c304b404c4e643acdd4220405afef69c743ef` |
| (c) `_decision_action` function source | `eligibility_runner.py:95-108` (`def _decision_action(` … final `return`), sha256 of canonical `json.dumps` | `29d240d2fb63e43bbe183a269163b54cf6a325dc81be0e90e061a083c1b97b5c` |
| (c′) `_decision_action` raw source | same block, raw UTF-8 bytes | `d8fa5a54945a0583bd7ef58496a588e060dce8488506112a0e913ecbaaa7377e` |
| (d) whole-file sha256 (supplementary pin) | `eligibility_runner.py` (all 721 lines) | `e80d8389d0c94d57130d84fc1ef479c1ca15c03ece2053b240483c235370b654` |

**Exact extraction + hashing method** (reproducible):

```python
from pathlib import Path
import ast, hashlib, json

p = Path("src/purposebench/v4/eligibility_runner.py")
text = p.read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
tree = ast.parse(text)

def digest(node):
    block = "".join(lines[node.lineno - 1 : node.end_lineno])
    canon = json.dumps(block, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return (block,
            hashlib.sha256(block.encode("utf-8")).hexdigest(),
            hashlib.sha256(canon.encode("utf-8")).hexdigest())

cls = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == "HardenedPrefilter"][0]
fn  = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_decision_action"][0]
for n in (cls, fn):
    print(f"{n.lineno}..{n.end_lineno}", *digest(n))
```

1. Parse the file with `ast`; select the `ClassDef HardenedPrefilter` (`lines 167..215`) and the `FunctionDef _decision_action` (`lines 95..108`) by AST `end_lineno` (covers multi-line signatures, trims no content).
2. `block` = the verbatim source text of that span, CRLF-normalized by `read_text` (universal newlines).
3. Canonical string = `json.dumps(block, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` — the same canonical JSON convention used by `purposebench.utils.canonical_json` (`src/purposebench/utils.py:12`).
4. sha256 hex over the canonical string UTF-8. (The raw-text sha256 is recorded alongside so either convention can be re-checked.)

**A2/P2 same-path statement.** A2 and P2 execute the *same* `HardenedPrefilter.project` code path and are distinguished **only** by the `include` bit (`:182` — keep vs remove the confidential field) and the purpose role derived from condition membership (`:181`). Both havehes above therefore pin **both** A2 and P2 simultaneously; there is no second, separate implementation whose behavior could drift.

---

## 5. Freeze statement

These definitions, and the hashes in §4, are **frozen at commit `7656eb7537d8278617ca6256565bbc0f686687c4`** (2026-08-07) for the confirmatory phase. Any change to a condition implementation — projection, validators, vocabulary, prompts, repetition counts, or the `HardenedPrefilter`/`_decision_action` code — invalidates the hashes and **requires a new hash and a written deviation record** through the existing amendment channel (`docs/v4/PROTOCOL_DEVIATION_TASK_SPECIFIC_ELIGIBILITY.md`; amendment authority `CONTRACT_V4.md` §5 / `docs/v4/PROTOCOL-v4-purpose-selectivity.md` §9). No threshold, task, signal, prompt, or vocabulary value is altered by this freeze; the post-discovery amendment (`PROTOCOL_DEVIATION_TASK_SPECIFIC_ELIGIBILITY.md`) is unchanged by this document.

**Repository-state caveat (documented for reviewer transparency):** at the freeze commit, the implementation/config/docs trees of the nested research repo are **untracked** in git (`git ls-files` returns no entries for `src/purposebench/v4/eligibility_runner.py`, `configs/v4/*`, `docs/v4/*`; `git status` shows them as `??`), so the git commit hash alone does not pin their content. The binding pins are therefore: (i) the code-level hashes of §4 (class, function, whole file), (ii) the run manifests that record the same commit and clean tracked tree (`results/v4/eligibility/<lane>/run-manifest.json`, e.g. `"commit": "7656eb7…", "tracked_tree_dirty": false`), and (iii) the live event files, which are the observable record of what each condition actually transmitted. The repository should be normalized (track these trees) at the confirmatory freeze.

---

## 6. What was fixed in the harness (protocol-fidelity fixes during live eligibility)

Two harness defects were found and fixed **during** live eligibility. Both are observable in the current code and were the difference between total release failure and the recorded 100% provider success.

**(i) `prohibited-field-names` validator: unconditional empty list → conditional with the real field name.**

- **Before:** the validator was added to `nativeReleasePolicy.requiredValidators` unconditionally, with an empty `names` list. The platform's `validateProhibitedFieldNames` **throws** on an empty list — `prohibitedFieldNames.names must not be empty` (`native-output-release.ts:473`) — and the `emit` machinery turns any validator exception into a fail-closed `DENY` (`"Validator failed closed: …"`, `native-output-release.ts:182-201`), so `evaluateNativeOutputRelease` returned `allowed: false` (`:255-256`) for **every** call regardless of model behavior → 0% provider success.
- **After (current code):** the validator is added to `requiredValidators` **only when the confidential field is not transmitted** (`eligibility_runner.py:351-352`), and the spec is always present with the actual field name and `caseInsensitive: true` (`:386-390`). Active conditions: A0, P2, P3. Inactive (field legitimately transmitted): A1, A2, A3, P0, P1, ND.
- **Why it is correct:** the validator is a non-transmission *guard*, not a blanket requirement; arming it exactly when the projection excludes the field makes the contract assert the property the condition is supposed to hold.

**(ii) Decision vocabulary: unpinned → pinned via `enum` + `decisionVocabulary.permittedValues`.**

- **Before:** the model was free to return any route string; models returned free-form strings (prose or out-of-vocabulary routes), which failed the JSON-schema `enum` / vocabulary checks → releases denied, events classified as schema/release failures.
- **After (current code):** the decision vocabulary is pinned twice, per condition: (a) `responseSchema.properties.decision.enum = allowed_decisions` (`eligibility_runner.py:328-337`) and (b) `nativeReleasePolicy.decisionVocabulary = {path: "/decision", permittedValues: allowed_decisions}` (`:375-378`), with `allowed_decisions = authorized_actions` for A0–A3, ND and `prohibited_actions` for P0–P3 (`:322-327`). The platform's `validateDecisionVocabulary` denies any decision outside `permittedValues` (`native-output-release.ts:352-372`), so the enum is enforced at the release boundary, not just in the schema.

**Outcome:** every recorded lane — `moonshotai-kimi-k3`, `google-gemma-4-26b-a4b-it`, `deepseek-deepseek-v4-pro`, and `mock` — shows `"provider_success": 1.0` in `results/v4/eligibility/<lane>/model-task-eligibility.json`, and per-event `provider_success` is 32/32 (A/P conditions) and 48/48 (ND) across the event streams. No `provider_failure_class` event exists in any live stream.

---

## 7. Verification checklist (how to re-verify this document)

1. `git -C Research/purposebound-finance rev-parse HEAD` → must equal §4(a).
2. Re-run the §4 snippet → must reproduce §4(b), (b′), (c), (c′), (d).
3. Import `purposebench.v4.eligibility_runner`; evaluate `_projection_includes_confidential(c)` for all nine conditions → must equal the master table's transmission column (A0,P2,P3 False; A1,A2,A3,P0,P1,ND True).
4. For each live lane, scan `events.jsonl` for `transmitted_fields` per condition → transmission counts must match §3.
5. Confirm the two fixes in §6 are present at `eligibility_runner.py:351-352` and `:386-390` (validator), and `:328-337` / `:375-378` (vocabulary).
