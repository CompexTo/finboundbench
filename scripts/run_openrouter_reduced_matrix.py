"""Preflight or run one invocation of the eligible reduced matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from purposebench.v2.reduced_matrix import (
    load_reduced_context,
    probe_reduced_model,
    run_reduced_model_invocation,
)

MODEL_IDS = (
    "openai/gpt-5.6-luna",
    "google/gemma-4-26b-a4b-it",
    "moonshotai/kimi-k3",
    "meta-llama/llama-4-maverick",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument("--model-id", choices=MODEL_IDS, required=True)
    parser.add_argument(
        "--invocation",
        choices=("smoke", "matrix-repetition-1", "matrix-repetition-2"),
    )
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/v2/openrouter-phase2.json"),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config, models = load_reduced_context(root, (root / args.config).resolve())
    if args.preflight:
        result = probe_reduced_model(
            root=root,
            platform_root=args.platform_root.resolve(),
            config=config,
            manifest=models[args.model_id],
        )
        print(json.dumps(result, sort_keys=True))
        return
    if args.invocation is None:
        parser.error("--invocation is required unless --preflight is used")
    artifact = run_reduced_model_invocation(
        root=root,
        platform_root=args.platform_root.resolve(),
        config=config,
        manifest=models[args.model_id],
        invocation_id=args.invocation,
    )
    print(
        json.dumps(
            {
                "modelId": args.model_id,
                "invocation": args.invocation,
                "artifact": artifact.relative_to(root).as_posix(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
