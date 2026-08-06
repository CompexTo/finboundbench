"""Verify the offline purpose-selective matrix schedule and protocol freeze."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v3.matrix import verify_matrix_dry_run, verify_protocol_freeze


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    schedule = verify_matrix_dry_run(research_root)
    freeze = verify_protocol_freeze(research_root, args.platform_root.resolve())
    print(
        json.dumps(
            {
                "scheduleStatus": schedule["status"],
                "scheduleHash": schedule["scheduleHash"],
                "cells": schedule["cells"],
                "freezeStatus": freeze["status"],
                "freezeManifestHash": freeze["freezeManifestHash"],
                "validationAnchor": freeze["validationAnchor"]["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
