from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

from purposebench.metrics.evaluate import evaluate_results
from purposebench.utils import read_jsonl

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def _save_figure(figure: Any, figures_dir: Path, name: str) -> list[Path]:
    paths = [figures_dir / f"{name}.pdf", figures_dir / f"{name}.svg"]
    for path in paths:
        figure.savefig(path, bbox_inches="tight")
    plt.close(figure)
    return paths


def _latex(frame: pd.DataFrame, path: Path) -> Path:
    path.write_text(
        frame.to_latex(index=False, float_format=lambda value: f"{value:.3f}"),
        encoding="utf-8",
    )
    return path


def build_report_assets(raw_path: Path, derived_dir: Path, paper_dir: Path) -> list[Path]:
    """Regenerate every paper asset starting from immutable raw JSONL."""

    evaluate_results(raw_path, derived_dir)
    figures = paper_dir / "figures"
    tables = paper_dir / "tables"
    generated = paper_dir / "generated"
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    generated.mkdir(parents=True, exist_ok=True)

    condition = pd.read_csv(derived_dir / "summary_by_condition.csv")
    workflow = pd.read_csv(derived_dir / "summary_by_workflow.csv")
    statistics = pd.read_csv(derived_dir / "statistical_tests.csv")
    exclusions = pd.read_csv(derived_dir / "exclusions.csv")
    outputs: list[Path] = []

    figure, axis = plt.subplots(figsize=(6.4, 4.2))
    axis.scatter(condition["utility"], 1 - condition["purpose_violation_rate"], s=70)
    for row in condition.itertuples(index=False):
        axis.annotate(row.condition, (row.utility, 1 - row.purpose_violation_rate), fontsize=8)
    axis.set(xlabel="Legitimate task utility", ylabel="1 - purpose violation rate")
    axis.grid(alpha=0.25)
    outputs.extend(_save_figure(figure, figures, "safety_versus_utility"))

    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    values = condition["purpose_violation_rate"]
    lower = values - condition["purpose_violation_ci95_low"]
    upper = condition["purpose_violation_ci95_high"] - values
    axis.bar(condition["condition"], values, yerr=[lower, upper], capsize=4)
    axis.set(ylabel="Purpose violation rate", ylim=(0, 1))
    axis.tick_params(axis="x", labelrotation=25)
    axis.grid(axis="y", alpha=0.25)
    outputs.extend(_save_figure(figure, figures, "purpose_violation_by_condition"))

    pivot = workflow.pivot(index="workflow", columns="condition", values="silent_influence_rate")
    figure, axis = plt.subplots(figsize=(8.0, 4.5))
    pivot.plot(kind="bar", ax=axis)
    axis.set(ylabel="Silent influence rate", xlabel="Workflow", ylim=(0, 1))
    axis.tick_params(axis="x", labelrotation=20)
    axis.legend(fontsize=7)
    axis.grid(axis="y", alpha=0.25)
    outputs.extend(_save_figure(figure, figures, "silent_influence_by_workflow"))

    main_columns = [
        "condition",
        "pairs",
        "purpose_violation_rate",
        "silent_influence_rate",
        "unauthorized_retrieval_rate",
        "explicit_disclosure_rate",
        "utility",
    ]
    outputs.append(_latex(condition[main_columns], tables / "main_results.tex"))
    outputs.append(_latex(condition, tables / "compex_controls_ablation.tex"))
    outputs.append(
        _latex(
            condition[
                [
                    "condition",
                    "pairs",
                    "median_latency_ms",
                    "p95_latency_ms",
                    "mean_estimated_cost",
                ]
            ],
            tables / "latency_cost.tex",
        )
    )
    outputs.append(
        _latex(
            condition[["condition", "pairs", "evidence_completeness"]],
            tables / "evidence_completeness.tex",
        )
    )
    outputs.append(_latex(statistics, tables / "statistical_tests.tex"))

    raw_rows = [
        row
        for row in read_jsonl(raw_path)
        if row.get("record_type", "execution") == "execution"
    ]
    failure_rows: list[dict[str, Any]] = []
    for exclusion in exclusions.head(20).to_dict(orient="records"):
        run = next(
            (row for row in raw_rows if row.get("run_id") == exclusion.get("run_id")),
            None,
        )
        failure_rows.append(
            {
                "run_id": exclusion.get("run_id"),
                "case_id": run.get("case_id") if run else None,
                "workflow": run.get("workflow") if run else None,
                "condition": exclusion.get("condition"),
                "reason": exclusion.get("reason"),
                "parsed_output": json.dumps((run or {}).get("parsed_output", {}), sort_keys=True),
            }
        )
    failure_frame = pd.DataFrame(failure_rows)
    if failure_frame.empty:
        failure_frame = pd.DataFrame(
            columns=["run_id", "case_id", "workflow", "condition", "reason", "parsed_output"]
        )
    outputs.append(_latex(failure_frame, tables / "failure_examples.tex"))

    statements: list[str] = [
        "# Traceable result statements",
        "",
        "Generated mechanically from `results/raw/runs.jsonl`. Each statement cites its derived table row.",
        "",
    ]
    for index, row in condition.iterrows():
        statements.append(
            f"- `summary_by_condition.csv` row {index + 2}: condition `{row['condition']}` "
            f"has {int(row['pairs'])} complete pairs, purpose-violation rate "
            f"{row['purpose_violation_rate']:.6f}, silent-influence rate "
            f"{row['silent_influence_rate']:.6f}, and utility {row['utility']:.6f}."
        )
    statements_path = generated / "result_statements.md"
    statements_path.write_text("\n".join(statements) + "\n", encoding="utf-8")
    outputs.append(statements_path)
    return outputs
