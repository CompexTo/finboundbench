"""Freeze the corrected v3 live protocol anchored on the one-pair validation gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.utils import git_commit
from purposebench.v3.matrix import (
    build_protocol_freeze,
    current_repository_bindings,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    platform_root = args.platform_root.resolve()
    freeze_path = research_root / "results/v3/manifests/protocol-v3-live-freeze.json"
    if freeze_path.exists():
        raise FileExistsError("protocol-v3-live-freeze.json already exists; append-only")
    bindings = current_repository_bindings(research_root, platform_root)
    freeze = build_protocol_freeze(
        research_root,
        platform_root,
        research_commit=bindings["researchCommit"],
        platform_commit=bindings["platformCommit"],
    )
    freeze_path.write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": freeze["status"],
                "researchCommit": git_commit(research_root),
                "platformCommit": git_commit(platform_root),
                "scheduleHashTaskA": freeze["schedule"]["taskA"]["scheduleHash"],
                "scheduleHashTaskB": freeze["schedule"]["taskB"]["scheduleHash"],
                "cells": (
                    freeze["schedule"]["taskA"]["cells"] + freeze["schedule"]["taskB"]["cells"]
                ),
                "freezeManifestHash": freeze["freezeManifestHash"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
