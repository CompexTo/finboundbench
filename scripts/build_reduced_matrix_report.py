"""Build the governed reduced frontier-matrix report."""

from __future__ import annotations

import json
from pathlib import Path

from purposebench.v2.pilots import write_new_v2_artifact
from purposebench.v2.reduced_analysis import build_reduced_matrix_report


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = build_reduced_matrix_report(root)
    destination = write_new_v2_artifact(
        root,
        Path("results/v2/derived/openrouter-reduced-governed-matrix.json"),
        report,
    )
    print(
        json.dumps(
            {
                "artifact": destination.relative_to(root).as_posix(),
                "status": report["status"],
                "passingModels": report["passingModelCount"],
                "failedModels": report["failedModelCount"],
                "budget": report["budget"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
