"""Verify the v3 one-pair B0/P3 OpenRouter validation run from raw evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v3.pair_validation import verify_pair_validation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    manifest = verify_pair_validation(research_root, args.platform_root.resolve())
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "attempts": manifest["attempts"],
                "released": manifest["released"],
                "committedEur": manifest["budget"]["committedEur"],
                "manifestHash": manifest["manifestHash"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()