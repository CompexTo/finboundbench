"""Run one bounded OpenRouter-only Claude compatibility gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v2.claude_compatibility import run_gate_zero, run_paid_gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument("--gate", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/v2/openrouter-phase2.json"),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = (root / args.config).resolve()
    if args.gate == 0:
        artifact = run_gate_zero(root, args.platform_root.resolve(), config)
    else:
        artifact = run_paid_gate(
            root,
            args.platform_root.resolve(),
            config,
            args.gate,
        )
    print(json.dumps({"gate": args.gate, "artifact": artifact.relative_to(root).as_posix()}))


if __name__ == "__main__":
    main()
