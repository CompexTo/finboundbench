"""Run or locally preflight one eligible OpenRouter position diagnostic."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v2.position_diagnostic import (
    load_position_context,
    probe_position_model,
    run_position_model,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument(
        "--model-id",
        choices=("openai/gpt-5.6-luna", "deepseek/deepseek-v4-pro"),
        required=True,
    )
    parser.add_argument("--layout")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/v2/openrouter-phase2.json"),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config, models = load_position_context(root, (root / args.config).resolve())
    if args.preflight:
        result = probe_position_model(
            root=root,
            platform_root=args.platform_root.resolve(),
            config=config,
            manifest=models[args.model_id],
            layout=args.layout,
        )
        print(json.dumps(result, sort_keys=True))
        return
    artifact = run_position_model(
        root=root,
        platform_root=args.platform_root.resolve(),
        config=config,
        manifest=models[args.model_id],
        layout=args.layout,
    )
    print(
        json.dumps(
            {
                "modelId": args.model_id,
                "artifact": artifact.relative_to(root).as_posix(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
