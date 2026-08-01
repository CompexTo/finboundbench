# PurposeBound-Finance

Reproducible experiment scaffold for:

> **Authorized to See, Forbidden to Use: Measuring Silent Cross-Purpose Influence in Financial AI Agents**

The benchmark tests whether a financial AI system uses data for a purpose that is not permitted, even when the same operator or organization is technically authorized to access that data.

## Core hypothesis

Traditional role-based access and prompt instructions do not reliably prevent cross-purpose use. A purpose-bound execution runtime that projects only permitted fields and emits auditable evidence should reduce purpose violations while retaining task utility.

## Conditions

1. `all_data_no_policy` — all fields are visible, no purpose rule.
2. `all_data_prompt_policy` — all fields are visible, with a prompt prohibition.
3. `output_guard_only` — all fields are visible, with post-output filtering.
4. `metadata_prefilter` — prohibited fields are removed before model access.
5. `compex_purpose_bound` — Compex enforces a machine-readable purpose contract and returns evidence.

## Primary novelty

Each benchmark item has a paired counterfactual. Authorized fields stay identical while one prohibited field changes. If the agent's structured financial decision changes, the benchmark records **silent cross-purpose influence**, even if no sensitive field is disclosed in the output.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .[dev]
cp .env.example .env
python -m purposebench.cli generate --cases-per-workflow 30 --seed 20260802
python -m purposebench.cli run --config configs/experiment.yaml --adapter mock --limit 4
python -m purposebench.cli evaluate
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` and copy the
environment file with `Copy-Item .env.example .env`.

## Connect Compex

The mapped adapter targets the local Compex REST API on port 4000. It uploads
one complete synthetic case, creates a field-access policy, obtains a
policy-checked Analyze projection, and runs the model agent inside a second
Compex execution. It fails closed if any required evidence is absent.

Build the research-owned agent image, then configure the uncommitted `.env`:

```bash
make build-agent
```

Required Compex variables are `COMPEX_BASE_URL`, `COMPEX_API_KEY`,
`COMPEX_ORG_ID`, and `COMPEX_WORKSPACE_ID`. The current Compex execution schema
persists container environment metadata, so commercial model API keys are
rejected by default. Use a local endpoint with a non-secret placeholder key for
the smoke/pilot or add secure secret-reference support to Compex in a separately
reviewed platform change.

Run:

```bash
python scripts/doctor.py
python -m purposebench.cli run --config configs/smoke_v4.yaml --limit 4
```

See `docs/COMPEX_LOCAL_MAPPING.md` for the exact interface, limitations, and
evidence semantics. The successful pre-freeze gate and the earlier preserved
failed attempts are documented in `docs/PILOT_VALIDATION.md` and
`docs/PROTOCOL_DEVIATIONS.md`.

## Reproducibility rules

- Never edit raw JSONL result files.
- Every run appends one immutable event record.
- Derived tables are regenerated from raw results.
- Store policy, prompt, dataset and Git hashes with every run.
- Use deterministic synthetic-data seeds.
- Record exact model identifiers and API versions.
- Treat LLM judges as secondary; primary outcomes are deterministic access, evidence, sentinel disclosure and paired decision changes.
- Regenerate paper assets from raw events with `python scripts/build_paper_assets.py`.

See `CODEX_MASTER_PROMPT.md` for the full implementation and execution brief.
