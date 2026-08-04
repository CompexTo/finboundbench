from pathlib import Path

import pytest

from purposebench.utils import sha256_file, sha256_json
from purposebench.v2.experiments import ExperimentCondition
from purposebench.v2.inference_pilot import condition_prompts, load_paired_records
from purposebench.v2.remote_pilot import (
    _node_binary,
    prepare_remote_batch,
    validate_remote_model_manifest,
)


def _dataset_path() -> Path:
    return Path("data/v2/generated/hmda-2024-dc-pairs.jsonl")


def test_remote_batch_denies_internal_fields_and_pseudonymizes_identifiers() -> None:
    dataset = _dataset_path()
    rows = load_paired_records(dataset, pair_limit=2)
    first, selected, denied, pseudonymized = prepare_remote_batch(
        rows,
        dataset_sha256=sha256_file(dataset),
    )
    second, _, _, _ = prepare_remote_batch(
        rows,
        dataset_sha256=sha256_file(dataset),
    )
    assert first == second
    assert set(denied).isdisjoint(selected)
    assert set(denied).isdisjoint(first[0])
    assert {"case_id", "lei", "source_record_id"}.issubset(pseudonymized)
    assert first[0]["case_id"].startswith("pseudo_")
    assert first[0]["case_id"] != rows[0]["case_id"]


def test_remote_prompt_uses_the_immutable_purpose_contract() -> None:
    prompt = condition_prompts(
        ExperimentCondition.COMPEX_GOVERNED_REMOTE,
        ("internal_fraud_note",),
    )["system"]
    assert "Immutable purpose contract" in prompt
    assert "No tools or network calls are authorized" in prompt


def test_one_record_remote_smoke_can_retain_an_incomplete_pair() -> None:
    rows = load_paired_records(_dataset_path(), pair_limit=1)[:1]
    assert len(rows) == 1
    assert len({str(row["pair_id"]) for row in rows}) == 1


def test_remote_bridge_resolves_a_supported_node_runtime() -> None:
    assert Path(_node_binary()).is_file()


def _remote_manifest() -> dict[str, object]:
    manifest: dict[str, object] = {
        "artifactSlug": "provider-model",
        "budgetCeilingUsdPerToken": {
            "prompt": "0.000001",
            "completion": "0.000002",
        },
        "canonicalSlug": "provider/model-20260804",
        "capturedAt": "2026-08-04T00:00:00Z",
        "contextSize": 4096,
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "metadataResponseSha256": "a" * 64,
        "modelId": "provider/model-20260804",
        "modelVersion": "provider/model-20260804",
        "provider": "OPENROUTER",
        "providerRouting": {
            "only": ["provider/region"],
            "allowFallbacks": False,
            "zeroDataRetention": True,
        },
        "routingEndpointSnapshotSha256": "b" * 64,
        "supportedParameters": [
            "max_completion_tokens",
            "response_format",
            "structured_outputs",
        ],
    }
    manifest["manifestHash"] = sha256_json(manifest)
    return manifest


def test_remote_manifest_accepts_provider_specific_output_token_parameter() -> None:
    manifest = _remote_manifest()
    assert validate_remote_model_manifest(manifest)["manifestHash"] == manifest["manifestHash"]


@pytest.mark.parametrize(
    "routing",
    [
        {"only": "provider", "allowFallbacks": False, "zeroDataRetention": True},
        {"only": ["provider"], "allowFallbacks": True, "zeroDataRetention": True},
        {"only": ["provider"], "allowFallbacks": False, "zeroDataRetention": False},
    ],
)
def test_remote_manifest_rejects_unbound_provider_routing(routing: object) -> None:
    manifest = _remote_manifest()
    manifest["providerRouting"] = routing
    manifest["manifestHash"] = sha256_json(
        {key: value for key, value in manifest.items() if key != "manifestHash"}
    )
    with pytest.raises(ValueError, match="provider route"):
        validate_remote_model_manifest(manifest)
