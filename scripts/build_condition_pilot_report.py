"""Build the controlled five-condition inference-pilot report."""

from __future__ import annotations

import json
from pathlib import Path

from purposebench.v2.condition_analysis import build_condition_pilot_report
from purposebench.v2.pilots import write_new_v2_artifact


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = build_condition_pilot_report(root)
    destination = write_new_v2_artifact(
        root,
        Path("results/v2/derived/openrouter-full-condition-pilot.json"),
        report,
    )
    print(
        json.dumps(
            {
                "artifact": destination.relative_to(root).as_posix(),
                "status": report["status"],
                "passedConditions": report["passedConditionCount"],
                "failedConditions": report["failedConditionCount"],
                "budget": report["budget"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
