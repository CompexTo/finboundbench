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
python -m purposebench.cli generate --cases-per-workflow 10
python -m purposebench.cli run --config configs/experiment.yaml --condition mock
python -m purposebench.cli evaluate
```

## Connect Compex

Edit `.env` and `configs/experiment.yaml`, then implement the small mapping in `src/purposebench/adapters/compex.py` to match your local Compex API or CLI. Run:

```bash
python scripts/doctor.py
python -m purposebench.cli run --config configs/experiment.yaml --condition compex_purpose_bound --limit 4
```

## Reproducibility rules

- Never edit raw JSONL result files.
- Every run appends one immutable event record.
- Derived tables are regenerated from raw results.
- Store policy, prompt, dataset and Git hashes with every run.
- Use deterministic synthetic-data seeds.
- Record exact model identifiers and API versions.
- Treat LLM judges as secondary; primary outcomes are deterministic access, evidence, sentinel disclosure and paired decision changes.

See `CODEX_MASTER_PROMPT.md` for the full implementation and execution brief.
