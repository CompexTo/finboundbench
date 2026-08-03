"""Run and record the focused protocol-v2-local attack suite."""

from __future__ import annotations

import argparse
from pathlib import Path

from purposebench.v2.attack_suite import run_local_attack_suite
from purposebench.v2.pilots import write_new_v2_artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/v2/raw/platform/local-attack-suite.json"),
    )
    args = parser.parse_args()
    benchmark_root = Path(__file__).resolve().parents[1]
    report = run_local_attack_suite(
        benchmark_root=benchmark_root,
        platform_root=args.platform_root.resolve(),
    )
    destination = write_new_v2_artifact(benchmark_root, args.output, report)
    print(f"{report['status']} {destination}")
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
