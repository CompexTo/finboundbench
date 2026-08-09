"""Evaluate the reference baselines on a split and write a leaderboard.

Usage (from the repository root):

    python competition/evaluator/run_baselines.py \
        --pairs data/v4/v4_calibr/pairs.jsonl \
        --manifest data/v4/v4_signal_manifest.json \
        --out competition/results/leaderboard_dev.json

Writes JSON and a human-readable Markdown table. No API key, no network.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from competition.baselines import BASELINES
from competition.evaluator.harness import (
    DockerSubmission,
    PythonSubmission,
    load_python_submission,
    run_submission,
)
from competition.evaluator.metrics import compute_metrics
from competition.evaluator.payloads import CONDITIONS, load_jsonl, load_manifest, render_split

REPO_ROOT = Path(__file__).resolve().parents[2]

ORACLE_LABEL_INJECTION = "oracle"


def score_submission(
    submission: Any,
    pairs: list[dict[str, Any]],
    signals: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    requests = render_split(pairs, signals, CONDITIONS)
    decisions = run_submission(
        submission,
        requests,
        inject_labels_for=ORACLE_LABEL_INJECTION,
    )
    return compute_metrics(pairs, decisions)


def build_leaderboard(results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, metrics in results.items():
        bacc = metrics["bacc"]
        rows.append(
            {
                "system": name,
                "bacc_A0": round(bacc["A0"], 4) if bacc["A0"] is not None else None,
                "bacc_A1": round(bacc["A1"], 4) if bacc["A1"] is not None else None,
                "bacc_A3": round(bacc["A3"], 4) if bacc["A3"] is not None else None,
                "AUR": round(metrics["aur"], 4) if metrics["aur"] is not None else None,
                "UIR_P0": round(metrics["uir"]["P0"], 4) if metrics["uir"]["P0"] is not None else None,
                "UIR_P2": round(metrics["uir"]["P2"], 4) if metrics["uir"]["P2"] is not None else None,
                "UIR_P3": round(metrics["uir"]["P3"], 4) if metrics["uir"]["P3"] is not None else None,
                "nd_floor": round(metrics["nd_floor"], 4) if metrics["nd_floor"] is not None else None,
                "net_ui": round(metrics["net_ui"], 4) if metrics["net_ui"] is not None else None,
                "availability": round(metrics["availability"], 4) if metrics["availability"] is not None else None,
                "policy_violations": metrics["policy_violations"],
                "cost_usd": round(metrics["total_cost_usd"], 4),
                "constraint_ok": metrics["constraint_ok"],
                "quality_ok": metrics["quality_ok"],
            }
        )
    return rows


def render_markdown(rows: list[dict[str, Any]]) -> str:
    header = (
        "| system | AUR | UIR_P0 | UIR_P2 | UIR_P3 | floor | net_ui | avail | viol | cost | pass |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|"
    )
    lines = [header]
    for row in rows:
        lines.append(
            "| {system} | {aur} | {u0} | {u2} | {u3} | {floor} | {net} | {avail} | {viol} | {cost} | {pass_} |".format(
                system=row["system"],
                aur=_fmt(row["AUR"]),
                u0=_fmt(row["UIR_P0"]),
                u2=_fmt(row["UIR_P2"]),
                u3=_fmt(row["UIR_P3"]),
                floor=_fmt(row["nd_floor"]),
                net=_fmt(row["net_ui"]),
                avail=_fmt(row["availability"]),
                viol=row["policy_violations"],
                cost=row["cost_usd"],
                pass_=("C+Q" if row["constraint_ok"] and row["quality_ok"] else "C" if row["constraint_ok"] else "Q" if row["quality_ok"] else "-"),
            )
        )
    return "\n".join(lines)


def _fmt(value) -> str:
    return f"{value:.4f}" if value is not None else "-"


def main() -> None:
    parser = argparse.ArgumentParser(description="FinBoundBench baseline evaluation")
    parser.add_argument("--pairs", default=str(REPO_ROOT / "data/v4/v4_calibr/pairs.jsonl"))
    parser.add_argument("--manifest", default=str(REPO_ROOT / "data/v4/v4_signal_manifest.json"))
    parser.add_argument("--out", default=str(REPO_ROOT / "competition/results/leaderboard_dev.json"))
    parser.add_argument("--submission", default=None, help="optional participant module with decide()")
    parser.add_argument(
        "--docker-base-url",
        default=None,
        help="optional container endpoint exposing POST /decide (e.g. http://127.0.0.1:8000)",
    )
    args = parser.parse_args()

    pairs = load_jsonl(args.pairs)
    manifest = load_manifest(args.manifest)
    signals = manifest["signals"]

    results: dict[str, dict[str, Any]] = {}
    for name, strategy in BASELINES.items():
        submission = PythonSubmission(strategy, name)
        results[name] = score_submission(submission, pairs, signals)

    if args.submission:
        submission = load_python_submission(args.submission)
        results[submission.name] = score_submission(submission, pairs, signals)

    if args.docker_base_url:
        submission = DockerSubmission(args.docker_base_url)
        results[submission.name] = score_submission(submission, pairs, signals)

    rows = build_leaderboard(results)
    report = {
        "pairs_path": str(Path(args.pairs).resolve()),
        "n_pairs": len(pairs),
        "n_signals": sorted({p["signal_id"] for p in pairs}),
        "leaderboard": rows,
        "note": "Development-split leaderboard. Lexicographic ranking: constraint first "
        "(net_ui <= 0.05, zero policy violations, availability >= 0.95), then AUR "
        "(quality gate >= 0.80). 'oracle' is a dev-only upper-bound reference with "
        "label access and never appears in final rankings.",
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path = out_path.with_suffix(".md")
    md_path.write_text(
        f"# FinBoundBench development leaderboard\n\n{render_markdown(rows)}\n",
        encoding="utf-8",
    )
    print(f"wrote {out_path}")
    print(render_markdown(rows))


if __name__ == "__main__":
    main()
