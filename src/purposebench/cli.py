from __future__ import annotations

import json
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich import print

from purposebench.dataset.generate import generate_dataset
from purposebench.harness.runner import run_experiment
from purposebench.metrics.evaluate import evaluate_results
from purposebench.reports.build import build_report_assets

app = typer.Typer(no_args_is_help=True)
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@app.command()
def generate(
    cases_per_workflow: int = typer.Option(30, min=1),
    seed: int = typer.Option(20260802),
) -> None:
    output = ROOT / "data" / "generated" / "cases.jsonl"
    manifest = generate_dataset(output, cases_per_workflow, seed)
    manifest["generator_sha256"] = __import__("hashlib").sha256(
        (ROOT / "src" / "purposebench" / "dataset" / "generate.py").read_bytes()
    ).hexdigest()
    manifest["policy_hashes"] = {
        path.stem: __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "policies").glob("*.yaml"))
    }
    manifest_path = ROOT / "results" / "manifests" / "dataset_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[green]Generated[/green] {manifest['records']} records at {output}")


@app.command()
def run(
    config: Path = typer.Option(Path("configs/experiment.yaml")),  # noqa: B008
    condition: str | None = typer.Option(None),
    limit: int | None = typer.Option(None, min=1),
    adapter: str | None = typer.Option(None, help="Use 'mock' only for harness testing"),
) -> None:
    config_path = config if config.is_absolute() else ROOT / config
    count = run_experiment(ROOT, config_path, condition, limit, adapter)
    print(f"[green]Recorded[/green] {count} new executions")


@app.command()
def evaluate() -> None:
    paths = evaluate_results(ROOT / "results" / "raw" / "runs.jsonl", ROOT / "results" / "derived")
    for name, path in paths.items():
        print(f"{name}: {path}")


@app.command()
def report() -> None:
    paths = build_report_assets(
        ROOT / "results" / "raw" / "runs.jsonl",
        ROOT / "results" / "derived",
        ROOT / "paper",
    )
    for path in paths:
        print(path)


if __name__ == "__main__":
    app()
