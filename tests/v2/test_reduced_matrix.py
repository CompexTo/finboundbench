from pathlib import Path

from purposebench.v2.reduced_matrix import (
    build_reduced_invocation,
    load_reduced_context,
    reduced_plan,
)


def test_reduced_matrix_excludes_failed_models_and_binds_budget() -> None:
    root = Path.cwd()
    config, models = load_reduced_context(
        root,
        root / "configs/v2/openrouter-phase2.json",
    )
    assert list(config["eligibleReducedMatrix"]["excludedModelIds"]) == [
        "anthropic/claude-opus-5",
        "deepseek/deepseek-v4-pro",
    ]
    assert set(models) == {
        "openai/gpt-5.6-luna",
        "google/gemma-4-26b-a4b-it",
        "moonshotai/kimi-k3",
        "meta-llama/llama-4-maverick",
    }
    assert reduced_plan(config) == [
        {"stage": "smoke", "repetition": 0, "recordCount": 1, "invocationId": "smoke"},
        {
            "stage": "matrix",
            "repetition": 1,
            "recordCount": 40,
            "invocationId": "matrix-repetition-1",
        },
        {
            "stage": "matrix",
            "repetition": 2,
            "recordCount": 40,
            "invocationId": "matrix-repetition-2",
        },
    ]


def test_reduced_contract_uses_governed_output_and_position_report() -> None:
    root = Path.cwd()
    config, models = load_reduced_context(
        root,
        root / "configs/v2/openrouter-phase2.json",
    )
    material = build_reduced_invocation(
        root=root,
        platform_root=root.parents[1],
        config=config,
        manifest=models["google/gemma-4-26b-a4b-it"],
        plan_item=reduced_plan(config)[1],
    )
    contract = material["contractMaterial"]
    assert contract["phase"] == "eligible_reduced_matrix"
    assert contract["recordCount"] == 40
    assert contract["repetition"] == 1
    assert contract["maximumAuthorizedCostEur"] == 0.1
    assert contract["positionDiagnosticReportHash"] == config["positionDiagnosticReportHash"]
    assert material["payload"]["actionPolicyHash"] == config["actionPolicyHash"]
    assert material["payload"]["maximumAuthorizedCostEur"] == 0.1
