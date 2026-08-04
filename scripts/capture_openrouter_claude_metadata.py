"""Capture immutable live OpenRouter catalog and ZDR route metadata."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from purposebench.utils import sha256_json
from purposebench.v2.openrouter_metadata import (
    CATALOG_URL,
    ZDR_ENDPOINTS_URL,
    build_claude_manifest,
    parse_metadata_response,
    response_sha256,
    select_claude_candidate,
    write_new_bytes,
)
from purposebench.v2.pilots import write_new_v2_artifact


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
    model, route, eligible = select_claude_candidate(catalog_rows, route_rows)
    metadata_dir = root / "results/v2/raw/metadata"
    catalog_path = metadata_dir / f"openrouter-models-{stamp}.json"
    route_path = metadata_dir / f"openrouter-zdr-endpoints-{stamp}.json"
    write_new_bytes(catalog_path, catalog_raw)
    write_new_bytes(route_path, route_raw)
    catalog_relative = catalog_path.relative_to(root).as_posix()
    route_relative = route_path.relative_to(root).as_posix()
    manifest = build_claude_manifest(
        model=model,
        route=route,
        captured_at=captured_at,
        catalog_artifact=catalog_relative,
        catalog_response_hash=response_sha256(catalog_raw),
        route_artifact=route_relative,
        route_response_hash=response_sha256(route_raw),
    )
    manifest_path = write_new_v2_artifact(
        root,
        Path(f"results/v2/manifests/openrouter-claude-model-{stamp}.json"),
        manifest,
    )
    selection = {
        "schemaVersion": "purposebound-finance.openrouter-claude-selection.v2",
        "capturedAt": captured_at,
        "catalogSource": CATALOG_URL,
        "catalogArtifact": catalog_relative,
        "catalogResponseHash": response_sha256(catalog_raw),
        "routeSource": ZDR_ENDPOINTS_URL,
        "routeArtifact": route_relative,
        "routeResponseHash": response_sha256(route_raw),
        "eligibleCandidates": eligible,
        "selectedModelId": manifest["modelId"],
        "selectedRoute": manifest["upstreamRoute"],
        "modelManifest": manifest_path.relative_to(root).as_posix(),
        "modelManifestHash": manifest["manifestHash"],
        "selectionReason": (
            "Highest live intelligence index among healthy Claude routes satisfying the "
            "ZDR, strict structured-output, context, and price filters."
        ),
        "selectionHash": "",
    }
    material = dict(selection)
    material.pop("selectionHash")
    selection["selectionHash"] = sha256_json(material)
    selection_path = write_new_v2_artifact(
        root,
        Path(f"results/v2/manifests/openrouter-claude-selection-{stamp}.json"),
        selection,
    )
    print(
        json.dumps(
            {
                "modelId": manifest["modelId"],
                "route": manifest["upstreamRoute"],
                "manifest": manifest_path.relative_to(root).as_posix(),
                "selection": selection_path.relative_to(root).as_posix(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
