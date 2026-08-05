"""Build the scoped protocol-v3 dry-run freeze manifest."""

import json
from pathlib import Path

from purposebench.utils import git_commit
from purposebench.v3.protocol import build_dry_run_freeze_manifest

if __name__ == "__main__":
    research_root = Path(__file__).resolve().parents[1]
    platform_root = research_root.parents[1]
    manifest = build_dry_run_freeze_manifest(
        research_root,
        platform_root,
        research_commit=git_commit(research_root),
        platform_commit=git_commit(platform_root),
    )
    output = research_root / (
        "results/v3/manifests/"
        "protocol-v3-psbe-no-tee-dry-run-freeze.json"
    )
    if output.exists():
        raise FileExistsError(f"freeze manifest already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"FROZEN_INSTRUMENTATION_ONLY {manifest['freezeManifestHash']}")
