"""Compute the not-confirmatory analysis payload for a live v3 matrix task run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from purposebench.v3.matrix import TASK_A, TASK_B
from purposebench.v3.matrix_analysis import AnalysisError, build_analysis, write_analysis


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=(TASK_A, TASK_B), default=TASK_A)
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    try:
        payload = build_analysis(research_root, args.task)
    except AnalysisError as exc:
        print(f"analysis failed closed: {exc}", file=sys.stderr)
        return 1
    manifest_path = write_analysis(research_root, args.task, payload)
    analysis_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "task": payload["task"],
                "manifestHash": payload["manifest"]["manifestHash"],
                "analysisHash": analysis_manifest["analysisHash"],
                "outcomes": payload["outcomes"],
                "totals": payload["totals"],
            },
            sort_keys=True,
        )
    )
    print(f"wrote: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
