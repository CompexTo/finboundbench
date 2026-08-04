"""Regenerate governed frontier pilot summaries from immutable raw artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v2.frontier_analysis import (
    analyze_frontier_pilots,
    write_frontier_analysis,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/v2/openrouter-frontier-matrix.json"),
    )
    args = parser.parse_args()
    benchmark_root = Path(__file__).resolve().parents[1]
    summaries, exclusions, manifest = analyze_frontier_pilots(
        benchmark_root,
        args.config.resolve(),
    )
    outputs = write_frontier_analysis(
        benchmark_root,
        summaries,
        exclusions,
        manifest,
    )
    print(
        json.dumps(
            {
                "passedPilotModels": len(summaries),
                "excludedPilotModels": len(exclusions),
                "committedCostEur": manifest["committedCostEur"],
                "outputs": {key: str(value) for key, value in outputs.items()},
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
