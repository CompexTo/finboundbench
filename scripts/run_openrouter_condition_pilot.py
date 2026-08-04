"""Preflight or run one controlled OpenRouter condition-pilot invocation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v2.condition_pilot import (
    CONDITIONS,
    load_condition_context,
    probe_condition_pilot,
    run_condition_invocation,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument("--condition", choices=CONDITIONS)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/v2/openrouter-phase2.json"),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config, model = load_condition_context(root, (root / args.config).resolve())
    if args.preflight:
        print(
            json.dumps(
                probe_condition_pilot(
                    root=root,
                    platform_root=args.platform_root.resolve(),
                    config=config,
                    manifest=model,
                ),
                sort_keys=True,
            )
        )
        return
    if args.condition is None:
        parser.error("--condition is required unless --preflight is used")
    artifact = run_condition_invocation(
        root=root,
        platform_root=args.platform_root.resolve(),
        config=config,
        manifest=model,
        condition=args.condition,
    )
    print(
        json.dumps(
            {
                "condition": args.condition,
                "artifact": artifact.relative_to(root).as_posix(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
