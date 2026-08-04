import json

import pytest

from purposebench.utils import sha256_json
from purposebench.v2.openrouter_metadata import (
    build_claude_manifest,
    parse_metadata_response,
    select_claude_candidate,
)


def model(model_id: str, intelligence: float) -> dict:
    return {
        "id": model_id,
        "canonical_slug": f"{model_id}-20260805",
        "created": 1,
        "context_length": 1_000_000,
        "supported_parameters": ["max_tokens", "response_format", "structured_outputs"],
        "reasoning": {
            "default_enabled": True,
            "supported_efforts": ["high", "low"],
        },
        "benchmarks": {"artificial_analysis": {"intelligence_index": intelligence}},
    }


def route(model_id: str, tag: str, uptime: float = 100) -> dict:
    return {
        "model_id": model_id,
        "model_name": model_id,
        "provider_name": "Amazon Bedrock",
        "tag": tag,
        "context_length": 1_000_000,
        "max_completion_tokens": 128_000,
        "supported_parameters": [
            "max_tokens",
            "reasoning",
            "reasoning_effort",
            "response_format",
            "structured_outputs",
        ],
        "pricing": {"prompt": "0.000005", "completion": "0.000025"},
        "uptime_last_5m": uptime,
    }


def test_selects_strongest_healthy_strict_claude_route_and_hashes_manifest() -> None:
    weaker = model("anthropic/claude-sonnet-test", 40)
    strongest = model("anthropic/claude-opus-test", 60)
    selected_model, selected_route, candidates = select_claude_candidate(
        [weaker, strongest],
        [route(weaker["id"], "amazon-bedrock/global"), route(strongest["id"], "amazon-bedrock")],
    )
    assert selected_model["id"] == strongest["id"]
    assert selected_route["tag"] == "amazon-bedrock"
    assert len(candidates) == 2
    manifest = build_claude_manifest(
        model=selected_model,
        route=selected_route,
        captured_at="2026-08-05T00:00:00+00:00",
        catalog_artifact="catalog.json",
        catalog_response_hash="a" * 64,
        route_artifact="routes.json",
        route_response_hash="b" * 64,
    )
    material = dict(manifest)
    observed = material.pop("manifestHash")
    assert observed == sha256_json(material)
    assert manifest["reasoningConfiguration"] == {
        "reasoningStrategy": "EFFORT",
        "reasoningEffort": "low",
    }
    assert manifest["fallbackAllowed"] is False


def test_rejects_mutable_unhealthy_or_non_strict_candidates() -> None:
    mutable = model("anthropic/claude-opus-latest", 100)
    fixed = model("anthropic/claude-opus-fixed", 90)
    non_strict = route(fixed["id"], "amazon-bedrock")
    non_strict["supported_parameters"].remove("structured_outputs")
    with pytest.raises(ValueError, match="No Claude endpoint"):
        select_claude_candidate(
            [mutable, fixed],
            [route(mutable["id"], "amazon-bedrock"), non_strict],
        )


def test_metadata_envelope_is_exact() -> None:
    raw = json.dumps({"data": [{"id": "anthropic/claude-test"}]}).encode()
    assert parse_metadata_response(raw, source="test")[0]["id"] == "anthropic/claude-test"
    with pytest.raises(ValueError, match="envelope"):
        parse_metadata_response(
            json.dumps({"data": [{"id": "x"}], "extra": True}).encode(),
            source="test",
        )
