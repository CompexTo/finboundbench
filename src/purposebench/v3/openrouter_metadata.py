"""Immutable OpenRouter metadata capture for protocol-v3 model admission.

Metadata GET calls are free; no paid inference is performed here. Manifests use
the v3 schema already consumed by the governed OpenRouter bridge.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import ROUND_CEILING, Decimal
from typing import Any

from purposebench.utils import sha256_json, sha256_text

CATALOG_URL = "https://openrouter.ai/api/v1/models"
ZDR_ENDPOINTS_URL = "https://openrouter.ai/api/v1/endpoints/zdr"
MANIFEST_SCHEMA = "purposebound-finance.openrouter-model-manifest.v3"
MUTABLE_ID = re.compile(
    r"(?:^|[-_.:/@])(latest|current|default|preview|auto)(?:$|[-_.:/@])",
    re.IGNORECASE,
)
ROUTE_TAG = re.compile(r"^[a-z0-9][a-z0-9-]*(?:/[a-z0-9][a-z0-9-]*)?$")
REQUIRED_ROUTE_PARAMETERS = frozenset(
    {"response_format", "structured_outputs"}
)
MIN_COMPLETION_TOKENS = 2_048
MIN_UPTIME_LAST_5M = 99.0
PRICE_CEILING_MULTIPLIER = Decimal("2")


def parse_metadata_response(raw: bytes, *, source: str) -> list[dict[str, Any]]:
    import json

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


def response_sha256(raw: bytes) -> str:
    return sha256_text(raw.decode("utf-8"))


def artifact_slug(model_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")


def _price_ceiling(value: Any) -> str:
    try:
        price = Decimal(str(value))
    except Exception as error:  # noqa: BLE001 - invalid provider pricing fails closed
        raise ValueError("OpenRouter route pricing is not numeric") from error
    if price < 0:
        raise ValueError("OpenRouter route pricing is negative")
    ceiling = (price * PRICE_CEILING_MULTIPLIER).quantize(
        Decimal("0.000000000001"), rounding=ROUND_CEILING
    )
    return format(ceiling.normalize(), "f")


def eligible_routes(
    model_id: str,
    catalog_rows: Sequence[Mapping[str, Any]],
    endpoint_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    models = [
        dict(row)
        for row in catalog_rows
        if str(row.get("id", "")) == model_id and not MUTABLE_ID.search(model_id)
    ]
    if len(models) != 1:
        raise ValueError(f"catalog identity for {model_id} is absent or duplicated")
    model = models[0]
    model_parameters = set(map(str, model.get("supported_parameters") or []))
    routes: list[dict[str, Any]] = []
    for route in endpoint_rows:
        if str(route.get("model_id", "")) != model_id:
            continue
        tag = str(route.get("tag", ""))
        parameters = set(map(str, route.get("supported_parameters") or []))
        uptime = route.get("uptime_last_5m")
        pricing = route.get("pricing")
        if not ROUTE_TAG.fullmatch(tag):
            continue
        if not REQUIRED_ROUTE_PARAMETERS.issubset(parameters):
            continue
        if not REQUIRED_ROUTE_PARAMETERS.issubset(model_parameters):
            continue
        if not isinstance(uptime, (int, float)) or isinstance(uptime, bool):
            continue
        if float(uptime) < MIN_UPTIME_LAST_5M:
            continue
        if not isinstance(route.get("max_completion_tokens"), int):
            continue
        if int(route["max_completion_tokens"]) < MIN_COMPLETION_TOKENS:
            continue
        if not isinstance(route.get("context_length"), int):
            continue
        if not isinstance(pricing, dict):
            continue
        try:
            prompt_price = Decimal(str(pricing["prompt"]))
            completion_price = Decimal(str(pricing["completion"]))
        except Exception:  # noqa: BLE001 - skip routes with unusable pricing
            continue
        if prompt_price < 0 or completion_price < 0:
            continue
        routes.append(dict(route))
    return model, routes


def select_route(
    model_id: str,
    catalog_rows: Sequence[Mapping[str, Any]],
    endpoint_rows: Sequence[Mapping[str, Any]],
    *,
    preferred_tag: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    model, routes = eligible_routes(model_id, catalog_rows, endpoint_rows)
    if not routes:
        raise ValueError(f"no ZDR route satisfies the v3 admission gate for {model_id}")
    chosen: dict[str, Any] | None = None
    if preferred_tag is not None:
        preferred = [route for route in routes if str(route.get("tag")) == preferred_tag]
        if len(preferred) == 1:
            chosen = preferred[0]
    if chosen is None:
        chosen = sorted(
            routes,
            key=lambda route: (
                -float(route["uptime_last_5m"]),
                str(route["tag"]),
            ),
        )[0]
    return model, chosen, routes


def build_model_manifest(
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
    if "max_tokens" in parameters:
        token_parameter = "max_tokens"
    elif "max_completion_tokens" in parameters:
        token_parameter = "max_completion_tokens"
    else:
        raise ValueError("route supports no output-token parameter")
    reasoning_configuration: dict[str, Any] | None = None
    reasoning_disable_strategy = "OMIT"
    if "reasoning" in parameters:
        reasoning_disable_strategy = "ENABLED_FALSE"
    pricing = route["pricing"]
    material = {
        "schemaVersion": MANIFEST_SCHEMA,
        "gateway": "OPENROUTER",
        "artifactSlug": artifact_slug(str(model["id"])),
        "modelId": model["id"],
        "modelVersion": model["id"],
        "canonicalCatalogSlug": model.get("canonical_slug"),
        "upstreamProvider": route.get("provider_name"),
        "upstreamRoute": route["tag"],
        "fallbackAllowed": False,
        "zeroDataRetentionRequired": True,
        "providerDataCollectionAllowed": False,
        "supportedParameters": parameters,
        "reasoningSetting": "DISABLED",
        "reasoningDisableStrategy": reasoning_disable_strategy,
        "tokenParameter": token_parameter,
        "structuredOutputMode": "JSON_SCHEMA_STRICT",
        "maximumOutputTokens": int(route["max_completion_tokens"]),
        "contextWindow": int(route["context_length"]),
        "inputPriceCeiling": _price_ceiling(pricing["prompt"]),
        "outputPriceCeiling": _price_ceiling(pricing["completion"]),
        "endpointMetadataCapturedAt": captured_at,
        "catalogArtifact": catalog_artifact,
        "catalogResponseHash": catalog_response_hash,
        "routeArtifact": route_artifact,
        "routeResponseHash": route_response_hash,
        "catalogMetadataHash": sha256_json(dict(model)),
        "routeMetadataHash": sha256_json(dict(route)),
        "routeUptimeLast5m": int(route["uptime_last_5m"]) if float(route["uptime_last_5m"]).is_integer() else float(route["uptime_last_5m"]),
        "routeCreated": route.get("created"),
        **({"reasoningConfiguration": reasoning_configuration} if reasoning_configuration else {}),
    }
    return {**material, "manifestHash": sha256_json(material)}


def write_new_bytes(path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value)
