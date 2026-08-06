"""Verify the offline purpose-selective matrix schedules and protocol freeze."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v3.matrix import (
    TASK_A,
    TASK_B,
    verify_matrix_dry_run,
    verify_protocol_freeze,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    schedules = {task: verify_matrix_dry_run(research_root, task=task) for task in (TASK_A, TASK_B)}
    freeze = verify_protocol_freeze(research_root, args.platform_root.resolve())
    print(
        json.dumps(
            {
                "scheduleStatus": schedules[TASK_A]["status"],
                "scheduleHashTaskA": schedules[TASK_A]["scheduleHash"],
                "cellsTaskA": schedules[TASK_A]["cells"],
                "scheduleHashTaskB": schedules[TASK_B]["scheduleHash"],
                "cellsTaskB": schedules[TASK_B]["cells"],
                "freezeStatus": freeze["status"],
                "freezeManifestHash": freeze["freezeManifestHash"],
                "validationAnchor": freeze["validationAnchor"]["status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
