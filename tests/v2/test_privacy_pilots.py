from pathlib import Path

import pytest

from purposebench.v2.pilots import (
    deterministic_training_data,
    run_privacy_attack_pilot,
    write_new_v2_artifact,
)


def test_training_data_is_deterministic_and_binary() -> None:
    first_x, first_y = deterministic_training_data()
    second_x, second_y = deterministic_training_data()

    assert first_x.shape == (512, 8)
    assert first_y.shape == (512,)
    assert (first_x == second_x).all()
    assert (first_y == second_y).all()
    assert set(first_y.tolist()) == {0, 1}


def test_privacy_attack_pilot_covers_required_conditions_and_attacks() -> None:
    report = run_privacy_attack_pilot()
    measurements = report["measurements"]

    assert len(measurements) == 15
    assert {item["condition"] for item in measurements} == {
        "ordinary",
        "governed_non_dp",
        "governed_dp",
    }
    assert len(report["comparisons"]) == 5


def test_v2_writer_rejects_v1_paths_and_overwrites(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="results/v2"):
        write_new_v2_artifact(
            tmp_path,
            Path("results/raw/pilot.json"),
            {"status": "invalid"},
        )

    path = write_new_v2_artifact(
        tmp_path,
        Path("results/v2/raw/privacy/pilot.json"),
        {"status": "ok"},
    )
    assert path.is_file()
    with pytest.raises(FileExistsError):
        write_new_v2_artifact(
            tmp_path,
            Path("results/v2/raw/privacy/pilot.json"),
            {"status": "duplicate"},
        )
