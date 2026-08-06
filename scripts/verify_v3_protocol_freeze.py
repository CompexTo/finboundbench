"""Verify the frozen v3 live protocol against the current repositories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v3.matrix import verify_protocol_freeze


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    freeze = verify_protocol_freeze(research_root, args.platform_root.resolve())
    print(
        json.dumps(
            {
                "status": freeze["status"],
                "freezeManifestHash": freeze["freezeManifestHash"],
                "validationAnchor": freeze["validationAnchor"]["status"],
                "cells": freeze["schedule"]["cells"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
