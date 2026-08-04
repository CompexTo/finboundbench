"""Build the deterministic governed-frontier comparison artifact."""

from __future__ import annotations

import json
from pathlib import Path

from purposebench.v2.frontier_report import (
    build_frontier_comparison,
    finalize_frontier_comparison,
)
from purposebench.v2.pilots import write_new_v2_artifact


def main() -> None:
    benchmark_root = Path(__file__).resolve().parents[1]
    comparison = finalize_frontier_comparison(
        build_frontier_comparison(
            benchmark_root,
            benchmark_root / "configs/v2/openrouter-frontier-matrix.json",
        )
    )
    destination = write_new_v2_artifact(
        benchmark_root,
        Path("results/v2/derived/openrouter-frontier-pilot-comparison.json"),
        comparison,
    )
    print(json.dumps({"output": str(destination), "comparisonHash": comparison["comparisonHash"]}))


if __name__ == "__main__":
    main()
