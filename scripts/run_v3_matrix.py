"""Run one purpose-selective matrix task live (paid, 1680 OpenRouter calls).

With ``--resume`` the driver continues an interrupted partial run from its
last hash-chained event; the interrupted attempt's ledger is archived and a
fresh ledger covers the resumed portion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v3.matrix import TASK_A, TASK_B, run_matrix


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument("--task", choices=(TASK_A, TASK_B), default=TASK_A)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    manifest = run_matrix(
        research_root, args.platform_root.resolve(), task=args.task, resume=args.resume
    )
    print(
        json.dumps(
            {
                "task": manifest["task"],
                "status": manifest["status"],
                "attempts": manifest["attempts"],
                "released": manifest["released"],
                "committedEur": manifest["budget"]["committedEur"],
                "finalEventHash": manifest["finalEventHash"],
                "manifestHash": manifest["manifestHash"],
            },
            sort_keys=True,
        )
    )
    if manifest["released"] != manifest["attempts"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
