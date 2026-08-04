"""Immutable OpenRouter metadata capture and Claude candidate selection."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from purposebench.utils import sha256_json, sha256_text

CATALOG_URL = "https://openrouter.ai/api/v1/models"
ZDR_ENDPOINTS_URL = "https://openrouter.ai/api/v1/endpoints/zdr"
MUTABLE_ID = re.compile(
    r"(?:^|[-_.:/@])(latest|current|default|preview|auto)(?:$|[-_.:/@])",
    re.IGNORECASE,
)
ROUTE_TAG = re.compile(r"^[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)?$")


def parse_metadata_response(raw: bytes, *, source: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"OpenRouter metadata is invalid JSON: {source}") from error
    if (
        not isinstance(value, dict)
        or "data" not in value
        or not set(value).issubset({"data", "links", "total_count"})
        or not isinstance(value["data"], list)
    ):
        raise ValueError(f"OpenRouter metadata envelope is invalid: {source}")
    if not value["data"]:
        raise ValueError(f"OpenRouter metadata is empty: {source}")
    if not all(isinstance(row, dict) for row in value["data"]):
        raise ValueError(f"OpenRouter metadata contains a non-object row: {source}")
    return [dict(row) for row in value["data"]]


def select_claude_candidate(
    catalog_rows: list[dict[str, Any]],
    endpoint_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    models = {
        str(row.get("id")): row
        for row in catalog_rows
        if str(row.get("id", "")).startswith("anthropic/claude-")
        and not MUTABLE_ID.search(str(row.get("id", "")))
    }
    eligible: list[dict[str, Any]] = []
    for route in endpoint_rows:
        model_id = str(route.get("model_id", ""))
        model = models.get(model_id)
        tag = str(route.get("tag", ""))
        parameters = set(map(str, route.get("supported_parameters") or []))
        uptime = route.get("uptime_last_5m")
        if (
            model is None
            or not ROUTE_TAG.fullmatch(tag)
            or not {"max_tokens", "response_format", "structured_outputs"}.issubset(parameters)
            or not isinstance(uptime, (int, float))
            or isinstance(uptime, bool)
            or float(uptime) < 99
            or not isinstance(route.get("max_completion_tokens"), int)
            or int(route["max_completion_tokens"]) < 2_048
        ):
            continue
        model_parameters = set(map(str, model.get("supported_parameters") or []))
        if not {"response_format", "structured_outputs"}.issubset(model_parameters):
            continue
        pricing = route.get("pricing")
        if not isinstance(pricing, dict):
            continue
        try:
            prompt_price = float(pricing["prompt"])
            completion_price = float(pricing["completion"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= prompt_price <= 0.00005 or not 0 <= completion_price <= 0.00025:
            continue
        benchmarks = model.get("benchmarks") or {}
        artificial = benchmarks.get("artificial_analysis") or {}
        strength = artificial.get("intelligence_index")
        eligible.append(
            {
                "modelId": model_id,
                "canonicalCatalogSlug": model.get("canonical_slug"),
                "route": tag,
                "provider": route.get("provider_name"),
                "uptimeLast5m": float(uptime),
                "uptimeLast30m": route.get("uptime_last_30m"),
                "intelligenceIndex": float(strength) if isinstance(strength, (int, float)) else 0.0,
                "created": int(model.get("created", 0)),
                "catalogMetadataHash": sha256_json(model),
                "routeMetadataHash": sha256_json(route),
            }
        )
    if not eligible:
        raise ValueError("No Claude endpoint satisfies the strict ZDR compatibility gate")
    eligible.sort(
        key=lambda row: (
            -row["intelligenceIndex"],
            -row["created"],
            -row["uptimeLast5m"],
            row["route"],
        )
    )
    chosen = eligible[0]
    model = models[str(chosen["modelId"])]
    routes = [
        route
        for route in endpoint_rows
        if route.get("model_id") == chosen["modelId"] and route.get("tag") == chosen["route"]
    ]
    if len(routes) != 1:
        raise ValueError("Selected Claude endpoint metadata is absent or duplicated")
    return model, routes[0], eligible


def build_claude_manifest(
    *,
    model: Mapping[str, Any],
    route: Mapping[str, Any],
    captured_at: str,
    catalog_artifact: str,
    catalog_response_hash: str,
    route_artifact: str,
    route_response_hash: str,
) -> dict[str, Any]:
    parameters = sorted(map(str, route["supported_parameters"]))
    reasoning = model.get("reasoning") or {}
    supported_efforts = set(map(str, reasoning.get("supported_efforts") or []))
    if "reasoning" in parameters and "reasoning_effort" in parameters and "low" in supported_efforts:
        reasoning_configuration: dict[str, Any] = {
            "reasoningStrategy": "EFFORT",
            "reasoningEffort": "low",
        }
    elif "reasoning" in parameters and reasoning.get("default_enabled") is False:
        reasoning_configuration = {
            "reasoningStrategy": "ENABLED_FLAG",
            "reasoningEnabled": False,
        }
    else:
        raise ValueError("Selected Claude route has no bounded reasoning configuration")
    pricing = route["pricing"]
    material = {
        "schemaVersion": "purposebound-finance.openrouter-model-manifest.v3",
        "gateway": "OPENROUTER",
        "modelId": model["id"],
        "canonicalCatalogSlug": model["canonical_slug"],
        "upstreamProvider": route["provider_name"],
        "upstreamRoute": route["tag"],
        "fallbackAllowed": False,
        "zeroDataRetentionRequired": True,
        "providerDataCollectionAllowed": False,
        "supportedParameters": parameters,
        "reasoningConfiguration": reasoning_configuration,
        "tokenParameter": "max_tokens",
        "structuredOutputMode": "JSON_SCHEMA_STRICT",
        "maximumOutputTokens": int(route["max_completion_tokens"]),
        "contextWindow": int(route["context_length"]),
        "inputPriceCeiling": str(pricing["prompt"]),
        "outputPriceCeiling": str(pricing["completion"]),
        "endpointMetadataCapturedAt": captured_at,
        "catalogArtifact": catalog_artifact,
        "catalogResponseHash": catalog_response_hash,
        "routeArtifact": route_artifact,
        "routeResponseHash": route_response_hash,
        "catalogMetadataHash": sha256_json(dict(model)),
        "routeMetadataHash": sha256_json(dict(route)),
    }
    return {**material, "manifestHash": sha256_json(material)}


def response_sha256(raw: bytes) -> str:
    return sha256_text(raw.decode("utf-8"))


def write_new_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value)
