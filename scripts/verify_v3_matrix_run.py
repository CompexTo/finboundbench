"""Verify one purpose-selective matrix task run from raw evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v3.matrix import TASK_A, TASK_B, verify_matrix_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument("--task", choices=(TASK_A, TASK_B), default=TASK_A)
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    manifest = verify_matrix_run(research_root, args.platform_root.resolve(), task=args.task)
    print(
        json.dumps(
            {
                "task": manifest["task"],
                "status": manifest["status"],
                "released": manifest["released"],
                "committedEur": manifest["budget"]["committedEur"],
                "manifestHash": manifest["manifestHash"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
