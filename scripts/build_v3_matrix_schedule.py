"""Build the offline purpose-selective matrix schedule for the v3 rebuild.

The schedule is computed from the frozen config and pair files; no provider
call is made and the resulting artifacts are append-only (the builder
refuses to overwrite an existing schedule).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v3.matrix import build_matrix_dry_run


def main() -> None:
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    manifest = build_matrix_dry_run(research_root)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "cells": manifest["cells"],
                "reservationTotalEur": manifest["reservationTotalEur"],
                "scheduleHash": manifest["scheduleHash"],
                "scheduleManifestHash": manifest["scheduleManifestHash"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
