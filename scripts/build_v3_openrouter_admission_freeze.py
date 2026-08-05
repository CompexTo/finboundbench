"""Build the v3 OpenRouter R0 admission freeze manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v3.remote_admission import (
    build_remote_admission_freeze,
    current_repository_bindings,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    platform_root = args.platform_root.resolve()
    bindings = current_repository_bindings(research_root, platform_root)
    manifest = build_remote_admission_freeze(
        research_root,
        platform_root,
        research_commit=bindings["researchCommit"],
        platform_commit=bindings["platformCommit"],
    )
    destination = research_root / "results/v3/manifests/openrouter-admission-v3-freeze.json"
    if destination.exists():
        existing = json.loads(destination.read_text(encoding="utf-8"))
        if existing.get("freezeManifestHash") != manifest["freezeManifestHash"]:
            raise FileExistsError(
                "a different R0 admission freeze already exists; refusing to overwrite"
            )
        print(json.dumps({"status": "already_frozen",
                          "freezeManifestHash": manifest["freezeManifestHash"]}, sort_keys=True))
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "frozen",
                      "freezeManifestHash": manifest["freezeManifestHash"]}, sort_keys=True))


if __name__ == "__main__":
    main()
