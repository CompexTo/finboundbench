"""Independently verify the v3 OpenRouter R0 admission run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v3.remote_admission import verify_remote_model_admission


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    manifest = verify_remote_model_admission(research_root, args.platform_root.resolve())
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "attempts": manifest["attempts"],
                "admitted": manifest["admitted"],
                "committedEur": manifest["budget"]["committedEur"],
                "manifestHash": manifest["manifestHash"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
