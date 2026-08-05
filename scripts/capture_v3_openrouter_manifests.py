"""Capture immutable live OpenRouter catalog and ZDR route metadata for v3.

Free GET calls only; no paid inference. Writes raw metadata under
results/v3/raw/metadata and one v3 manifest per candidate under
docs/v3/model-manifests. Existing manifests are never overwritten; a manifest
whose hash already exists is reported as unchanged.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from purposebench.utils import sha256_json
from purposebench.v3.openrouter_metadata import (
    CATALOG_URL,
    ZDR_ENDPOINTS_URL,
    artifact_slug,
    build_model_manifest,
    parse_metadata_response,
    response_sha256,
    select_route,
    write_new_bytes,
)

CANDIDATES: tuple[dict[str, str | None], ...] = (
    {"modelId": "openai/gpt-5.6-luna", "preferredRoute": "azure"},
    {"modelId": "moonshotai/kimi-k3", "preferredRoute": "morph"},
    {"modelId": "meta-llama/llama-4-maverick", "preferredRoute": "deepinfra/base"},
    {"modelId": "google/gemma-4-26b-a4b-it", "preferredRoute": "nextbit/bf16"},
    {"modelId": "deepseek/deepseek-v4-pro", "preferredRoute": "parasail/fp8"},
)
CLAUDE_REEVALUATION_PREFIX = "anthropic/claude-"
CLAUDE_V2_FAILED_MODEL = "anthropic/claude-opus-4.8"
CLAUDE_V2_FAILED_ROUTE = "amazon-bedrock"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    captured = datetime.now(UTC)
    stamp = captured.strftime("%Y%m%dT%H%M%SZ")
    captured_at = captured.isoformat()
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        catalog_response = client.get(CATALOG_URL, headers={"accept": "application/json"})
        route_response = client.get(ZDR_ENDPOINTS_URL, headers={"accept": "application/json"})
    catalog_response.raise_for_status()
    route_response.raise_for_status()
    catalog_raw = catalog_response.content
    route_raw = route_response.content
    catalog_rows = parse_metadata_response(catalog_raw, source=CATALOG_URL)
    route_rows = parse_metadata_response(route_raw, source=ZDR_ENDPOINTS_URL)
    metadata_dir = root / "results/v3/raw/metadata"
    catalog_path = metadata_dir / f"openrouter-models-{stamp}.json"
    route_path = metadata_dir / f"openrouter-zdr-endpoints-{stamp}.json"
    write_new_bytes(catalog_path, catalog_raw)
    write_new_bytes(route_path, route_raw)
    catalog_relative = catalog_path.relative_to(root).as_posix()
    route_relative = route_path.relative_to(root).as_posix()
    catalog_hash = response_sha256(catalog_raw)
    route_hash = response_sha256(route_raw)

    captures: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []
    for candidate in CANDIDATES:
        model_id = str(candidate["modelId"])
        preferred = candidate["preferredRoute"]
        try:
            model, route, routes = select_route(
                model_id,
                catalog_rows,
                route_rows,
                preferred_tag=preferred if isinstance(preferred, str) else None,
            )
            manifest = build_model_manifest(
                model=model,
                route=route,
                captured_at=captured_at,
                catalog_artifact=catalog_relative,
                catalog_response_hash=catalog_hash,
                route_artifact=route_relative,
                route_response_hash=route_hash,
            )
            slug = artifact_slug(model_id)
            manifest_path = root / "docs/v3/model-manifests" / f"openrouter-{slug}.json"
            if manifest_path.exists():
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
                if existing.get("manifestHash") == manifest["manifestHash"]:
                    status = "unchanged"
                else:
                    raise FileExistsError(
                        f"manifest drift for {model_id}; retire the old manifest explicitly"
                    )
            else:
                manifest_path.write_text(
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                status = "captured"
            captures.append(
                {
                    "modelId": model_id,
                    "route": manifest["upstreamRoute"],
                    "preferredRouteHonored": manifest["upstreamRoute"] == preferred,
                    "eligibleRouteCount": len(routes),
                    "manifestPath": manifest_path.relative_to(root).as_posix(),
                    "manifestHash": manifest["manifestHash"],
                    "inputPriceCeiling": manifest["inputPriceCeiling"],
                    "outputPriceCeiling": manifest["outputPriceCeiling"],
                    "status": status,
                }
            )
        except (ValueError, FileExistsError) as error:
            failures.append({"modelId": model_id, "error": str(error)})

    claude_candidates = sorted(
        {
            str(route.get("model_id"))
            for route in route_rows
            if str(route.get("model_id", "")).startswith(CLAUDE_REEVALUATION_PREFIX)
        }
    )
    claude_materially_different = [
        model_id
        for model_id in claude_candidates
        if model_id != CLAUDE_V2_FAILED_MODEL
    ]
    claude_decision = {
        "v2FailedModel": CLAUDE_V2_FAILED_MODEL,
        "v2FailedRoute": CLAUDE_V2_FAILED_ROUTE,
        "liveClaudeZdrModels": claude_candidates,
        "materiallyDifferentCandidates": claude_materially_different,
        "admissionDecision": (
            "EXCLUDED_NO_MATERIALLY_DIFFERENT_CANDIDATE"
            if not claude_materially_different
            else "ELIGIBLE_FOR_SEPARATE_GATE_REEVALUATION"
        ),
        "priorFailuresPreserved": True,
    }
    report = {
        "schemaVersion": "finboundbench.openrouter-capture.v3",
        "capturedAt": captured_at,
        "catalogArtifact": catalog_relative,
        "catalogResponseHash": catalog_hash,
        "routeArtifact": route_relative,
        "routeResponseHash": route_hash,
        "paidInferenceCalls": 0,
        "captures": captures,
        "failures": failures,
        "claudeReevaluation": claude_decision,
    }
    report["captureReportHash"] = sha256_json(report)
    report_path = metadata_dir / f"openrouter-v3-capture-{stamp}.json"
    with report_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"report": report_path.relative_to(root).as_posix(),
                      "captured": len(captures),
                      "failures": failures,
                      "claude": claude_decision["admissionDecision"]}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
