from pathlib import Path

from purposebench.v2.inference_pilot import load_paired_records
from purposebench.v2.position_diagnostic import (
    build_position_invocation,
    load_position_context,
    position_layouts,
)


def test_position_layouts_cover_required_diagnostics() -> None:
    rows = load_paired_records(
        Path("data/v2/generated/hmda-2024-dc-pairs.jsonl"),
        pair_limit=20,
    )
    plan = position_layouts(rows, pair_count=4, seed=20260805)
    assert len(plan) == 11
    assert {item["layout"] for item in plan} == {
        "original_order",
        "reversed_order",
        "deterministic_shuffle",
        "adjacent_pairs",
        "separated_pairs",
        "swapped_ab_positions",
        "singleton_calls",
        "small_batches",
        "full_batch",
    }
    assert len({item["invocationId"] for item in plan}) == len(plan)
    assert [row["case_id"] for row in plan[1]["rows"]] == [
        row["case_id"] for row in reversed(rows[:8])
    ]
    separated = next(item for item in plan if item["layout"] == "separated_pairs")
    assert [row["variant"] for row in separated["rows"]] == ["A"] * 4 + ["B"] * 4
    swapped = next(item for item in plan if item["layout"] == "swapped_ab_positions")
    assert [row["variant"] for row in swapped["rows"]] == ["B", "A"] * 4


def test_position_contract_binds_layout_action_policy_and_route() -> None:
    root = Path.cwd()
    platform_root = root.parents[1]
    config, models = load_position_context(
        root,
        root / "configs/v2/openrouter-phase2.json",
    )
    rows = load_paired_records(root / config["dataset"], pair_limit=20)
    invocation = position_layouts(rows, pair_count=4, seed=20260805)[0]
    material = build_position_invocation(
        root=root,
        platform_root=platform_root,
        config=config,
        manifest=models["openai/gpt-5.6-luna"],
        invocation=invocation,
    )
    contract = material["contractMaterial"]
    assert contract["phase"] == "eligible_position_diagnostic"
    assert contract["layout"] == "original_order"
    assert contract["upstreamRoute"] == "azure"
    assert contract["actionPolicyHash"] == config["actionPolicyHash"]
    assert contract["retryCount"] == 0
    assert material["payload"]["actionPolicyHash"] == config["actionPolicyHash"]
    assert material["payload"]["maximumAuthorizedCostEur"] == 0.05
