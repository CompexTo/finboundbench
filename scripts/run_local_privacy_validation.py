"""Run and retain the protocol-v2-local CPU privacy validations."""

from __future__ import annotations

import argparse
from pathlib import Path

from purposebench.v2.pilots import (
    run_privacy_attack_pilot,
    run_training_pilot,
    write_new_v2_artifact,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--training-output",
        type=Path,
        default=Path("results/v2/raw/privacy/dp-training-phase2-validation.json"),
    )
    parser.add_argument(
        "--attack-output",
        type=Path,
        default=Path("results/v2/raw/privacy/privacy-attack-phase2-validation.json"),
    )
    args = parser.parse_args()
    benchmark_root = Path(__file__).resolve().parents[1]

    training = run_training_pilot()
    attack = run_privacy_attack_pilot()
    training_path = write_new_v2_artifact(
        benchmark_root,
        args.training_output,
        training,
    )
    attack_path = write_new_v2_artifact(
        benchmark_root,
        args.attack_output,
        attack,
    )
    print(f"passed {training_path}")
    print(f"passed {attack_path}")


if __name__ == "__main__":
    main()
