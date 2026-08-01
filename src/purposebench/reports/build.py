from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_report_assets(derived_dir: Path, paper_dir: Path) -> list[Path]:
    paper_dir.mkdir(parents=True, exist_ok=True)
    tables = paper_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    summary = pd.read_csv(derived_dir / "summary_by_condition.csv")
    path = tables / "main_results.tex"
    path.write_text(summary.to_latex(index=False, float_format=lambda x: f"{x:.3f}"), encoding="utf-8")
    return [path]
