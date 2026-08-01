from pathlib import Path

import yaml

from purposebench.dataset.generate import generate_dataset
from purposebench.harness.runner import run_experiment
from purposebench.metrics.evaluate import evaluate_results


def test_mock_pipeline(tmp_path: Path) -> None:
    # Use repository policy files while placing generated data/results in a temporary clone-like root.
    repo = Path(__file__).resolve().parents[1]
    (tmp_path / "policies").mkdir()
    for src in (repo / "policies").glob("*.yaml"):
        (tmp_path / "policies" / src.name).write_text(src.read_text())
    (tmp_path / "data/generated").mkdir(parents=True)
    generate_dataset(tmp_path / "data/generated/cases.jsonl", 1, 123)
    config = {
        "experiment_name": "test",
        "seed": 123,
        "dataset_path": "data/generated/cases.jsonl",
        "results_path": "results/raw/runs.jsonl",
        "conditions": ["all_data_no_policy", "metadata_prefilter"],
        "models": [{"provider": "mock", "name": "mock"}],
        "repetitions": 1,
        "resume": True,
    }
    (tmp_path / "configs").mkdir()
    config_path = tmp_path / "configs/test.yaml"
    config_path.write_text(yaml.safe_dump(config))
    run_experiment(tmp_path, config_path, forced_adapter="mock")
    paths = evaluate_results(tmp_path / "results/raw/runs.jsonl", tmp_path / "results/derived")
    assert paths["summary"].exists()
