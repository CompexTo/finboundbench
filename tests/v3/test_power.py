from __future__ import annotations

import json
from pathlib import Path

import pytest

from purposebench.v3.power import (
    exact_mcnemar_power,
    minimum_pairs_for_power,
    protocol_v3_power_report,
)


def test_registered_power_values_are_stable() -> None:
    report = protocol_v3_power_report()
    rows = {row["name"]: row for row in report["scenarios"]}
    assert rows["h4_strong"]["power"]["200"] == pytest.approx(0.982642)
    assert rows["h4_conservative"]["power"]["200"] == pytest.approx(0.861093)
    assert rows["h1_authorized_utility"]["power"]["200"] == pytest.approx(
        0.906332
    )
    assert rows["h4_conservative"]["minimumPairsFor80Percent"] == 175
    assert rows["h1_authorized_utility"]["minimumPairsFor80Percent"] == 146


def test_checked_in_power_report_matches_executable_analysis() -> None:
    root = Path(__file__).parents[2]
    retained = json.loads(
        (root / "results/v3/statistics/power-analysis.json").read_text(
            encoding="utf-8"
        )
    )
    assert retained == protocol_v3_power_report()


def test_power_input_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        exact_mcnemar_power(0, 0.2, 0.1)
    with pytest.raises(ValueError, match="sum above 1"):
        exact_mcnemar_power(100, 0.8, 0.3)
    with pytest.raises(ValueError, match="unsupported"):
        exact_mcnemar_power(100, 0.2, 0.1, alternative="less")  # type: ignore[arg-type]


def test_minimum_power_is_first_crossing() -> None:
    n_pairs = minimum_pairs_for_power(0.8, 0.14, 0.04, alpha=0.025)
    assert exact_mcnemar_power(n_pairs, 0.14, 0.04, alpha=0.025) >= 0.8
    assert exact_mcnemar_power(n_pairs - 1, 0.14, 0.04, alpha=0.025) < 0.8
