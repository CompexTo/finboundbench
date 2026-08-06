"""Build the frozen one-pair validation manifest for the v3 OpenRouter gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v3.pair_validation import (
    build_pair_validation_freeze,
    current_repository_bindings,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    bindings = current_repository_bindings(research_root, args.platform_root.resolve())
    freeze = build_pair_validation_freeze(
        research_root,
        args.platform_root.resolve(),
        research_commit=bindings["researchCommit"],
        platform_commit=bindings["platformCommit"],
    )
    output = args.output if args.output.is_absolute() else research_root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"freezeManifestHash": freeze["freezeManifestHash"]}))


if __name__ == "__main__":
    main()