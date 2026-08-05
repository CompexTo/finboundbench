"""Re-capture manifests for models that failed R0 admission."""
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

MANIFEST_DIR = Path("docs/v3/model-manifests")

FAILED_MODELS = [
    ("openai/gpt-5.6-luna", "azure"),
    ("moonshotai/kimi-k3", "morph"),
    ("meta-llama/llama-4-maverick", "deepinfra/base"),
    ("google/gemma-4-26b-a4b-it", "siliconflow/fp8"),
]

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        catalog_response = client.get(CATALOG_URL, headers={"accept": "application/json"})
        route_response = client.get(ZDR_ENDPOINTS_URL, headers={"accept": "application/json"})
    catalog_response.raise_for_status()
    route_response.raise_for_status()
    catalog_raw = catalog_response.content
    route_raw = route_response.content
    catalog_rows = parse_metadata_response(catalog_raw, source="catalog")
    route_rows = parse_metadata_response(route_raw, source="endpoints")
    catalog_hash = response_sha256(catalog_raw)
    route_hash = response_sha256(route_raw)
    captured_at = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    catalog_relative = "docs/v3/model-manifests/openrouter-catalog-snapshot.json"
    route_relative = "docs/v3/model-manifests/openrouter-zdr-endpoints-snapshot.json"
    cat_path = root / catalog_relative
    if cat_path.exists():
        cat_path.unlink()
    cat_path.parent.mkdir(parents=True, exist_ok=True)
    write_new_bytes(cat_path, catalog_raw)
    rt_path = root / route_relative
    if rt_path.exists():
        rt_path.unlink()
    write_new_bytes(rt_path, route_raw)

    for model_id, preferred_tag in FAILED_MODELS:
        model, route, _ = select_route(model_id, catalog_rows, route_rows, preferred_tag=preferred_tag)
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
        dest = root / MANIFEST_DIR / f"openrouter-{slug}.json"
        if dest.exists():
            existing = json.loads(dest.read_text(encoding="utf-8"))
            if existing.get("manifestHash") == manifest["manifestHash"]:
                print(f"Unchanged {model_id}: hash={manifest['manifestHash'][:16]}...")
                continue
            dest.unlink()
        dest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Re-captured {model_id}: hash={manifest['manifestHash'][:16]}..., route={route['tag']}")

if __name__ == "__main__":
    main()
