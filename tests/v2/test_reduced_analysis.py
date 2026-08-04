import json
from pathlib import Path

from purposebench.utils import sha256_json
from purposebench.v2.reduced_analysis import build_reduced_matrix_report


def test_reduced_matrix_report_is_reproducible() -> None:
    root = Path.cwd()
    report = build_reduced_matrix_report(root)
    assert report["status"] == "COMPLETE_WITH_MODEL_FAILURE"
    assert report["passingModelCount"] == 3
    assert report["failedModelCount"] == 1
    by_model = {model["modelId"]: model for model in report["models"]}
    assert by_model["openai/gpt-5.6-luna"]["status"] == "PASSED"
    assert by_model["moonshotai/kimi-k3"]["status"] == "PASSED"
    assert by_model["meta-llama/llama-4-maverick"]["status"] == "PASSED"
    assert by_model["google/gemma-4-26b-a4b-it"]["status"] == (
        "FAILED_CLOSED_AFTER_SMOKE"
    )
    assert len(report["crossModelAgreement"]) == 3
    assert report["budget"]["categoryCommittedEur"] == 0.26121234
    assert report["budget"]["globalCommittedEur"] == 8.76316818
    material = dict(report)
    observed = material.pop("reportHash")
    assert observed == sha256_json(material)

    stored_path = root / "results/v2/derived/openrouter-reduced-governed-matrix.json"
    if stored_path.exists():
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        assert stored == report
