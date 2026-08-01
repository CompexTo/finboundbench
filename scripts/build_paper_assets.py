from pathlib import Path

from purposebench.reports.build import build_report_assets

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    for output in build_report_assets(
        ROOT / "results" / "raw" / "runs.jsonl",
        ROOT / "results" / "derived",
        ROOT / "paper",
    ):
        print(output)
