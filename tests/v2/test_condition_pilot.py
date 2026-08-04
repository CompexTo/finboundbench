from pathlib import Path

from purposebench.v2.condition_pilot import (
    CONDITIONS,
    build_condition_invocation,
    load_condition_context,
    prepare_condition_records,
)
from purposebench.v2.inference_pilot import load_paired_records


def test_condition_projection_and_controlled_exposure_are_exact() -> None:
    root = Path.cwd()
    rows = load_paired_records(
        root / "data/v2/generated/hmda-2024-dc-pairs.jsonl",
        pair_limit=4,
    )
    dataset_hash = "a" * 64
    full, full_fields, denied, full_pseudonyms = prepare_condition_records(
        rows,
        condition="all_data_no_policy",
        dataset_sha256=dataset_hash,
    )
    projected, projected_fields, projected_denied, projected_pseudonyms = (
        prepare_condition_records(
            rows,
            condition="compex_governed_projection",
            dataset_sha256=dataset_hash,
        )
    )
    assert set(denied).issubset(full_fields)
    assert set(projected_denied).isdisjoint(projected_fields)
    assert len(full[0]) > len(projected[0])
    assert full_pseudonyms == projected_pseudonyms == (
        "case_id",
        "lei",
        "source_record_id",
    )


def test_condition_contract_binds_consent_release_and_action_policy() -> None:
    root = Path.cwd()
    config, model = load_condition_context(
        root,
        root / "configs/v2/openrouter-phase2.json",
    )
    assert tuple(config["fullConditionPilot"]["conditions"]) == CONDITIONS
    full = build_condition_invocation(
        root=root,
        platform_root=root.parents[1],
        config=config,
        manifest=model,
        condition="all_data_no_policy",
    )
    native = build_condition_invocation(
        root=root,
        platform_root=root.parents[1],
        config=config,
        manifest=model,
        condition="compex_projection_plus_native_release",
    )
    assert full["prohibitedSyntheticFieldsTransmitted"] is True
    assert native["prohibitedSyntheticFieldsTransmitted"] is False
    assert full["releasePolicyMode"] == "NATIVE_COMPEX_SCHEMA_BOUND"
    assert native["releasePolicyMode"] == "NATIVE_COMPEX_FULL"
    assert full["contractMaterial"]["controlledExposureConsentHash"] == (
        config["fullConditionPilot"]["controlledExposureConsentHash"]
    )
    assert native["payload"]["actionPolicyHash"] == config["actionPolicyHash"]
    assert native["payload"]["maximumAuthorizedCostEur"] == 0.2
