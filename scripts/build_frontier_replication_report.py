"""Regenerate the governed frontier replication report."""

from pathlib import Path

from purposebench.v2.frontier_replication import (
    build_frontier_replication_report,
    write_frontier_replication_report,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = build_frontier_replication_report(
        root,
        root / "configs/v2/openrouter-frontier-matrix.json",
    )
    paths = write_frontier_replication_report(root, report)
    print(
        {
            "successfulAttempts": report["successfulAttempts"],
            "failedClosedAttempts": report["failedClosedAttempts"],
            "committedCostEur": report["budget"]["committedEur"],
            "artifacts": {key: str(value) for key, value in paths.items()},
        }
    )


if __name__ == "__main__":
    main()
