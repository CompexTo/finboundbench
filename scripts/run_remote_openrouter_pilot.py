"""Run the checkpointed protocol-v2 OpenRouter fallback pilot."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from purposebench.v2.pilots import write_new_v2_artifact
from purposebench.v2.remote_pilot import build_remote_manifest, run_remote_pilot


def _image_digest(image: str) -> str:
    try:
        output = subprocess.check_output(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        image_ids = subprocess.check_output(
            [
                "docker",
                "image",
                "ls",
                "--filter",
                f"reference={image}",
                "--format",
                "{{.ID}}",
            ],
            text=True,
        ).splitlines()
        if len(image_ids) != 1:
            raise RuntimeError("governed gate image tag is not uniquely installed") from None
        output = subprocess.check_output(
            ["docker", "image", "inspect", image_ids[0], "--format", "{{.Id}}"],
            text=True,
        ).strip()
    if not output.startswith("sha256:") or len(output) != 71:
        raise RuntimeError("governed gate image has no immutable local digest")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--pairs", type=int, required=True)
    parser.add_argument("--raw-name", required=True)
    parser.add_argument("--manifest-name", required=True)
    parser.add_argument("--local-fallback", type=Path, required=True)
    parser.add_argument("--image", default="purposebound-finance-v2-gate:local")
    args = parser.parse_args()
    benchmark_root = Path(__file__).resolve().parents[1]
    raw_path = run_remote_pilot(
        benchmark_root=benchmark_root,
        platform_root=args.platform_root.resolve(),
        dataset_path=args.dataset.resolve(),
        pair_limit=args.pairs,
        output_name=args.raw_name,
        workload_image_digest=_image_digest(args.image),
    )
    manifest = build_remote_manifest(
        benchmark_root,
        raw_path,
        args.local_fallback.resolve(),
    )
    destination = write_new_v2_artifact(
        benchmark_root,
        Path("results/v2/manifests") / args.manifest_name,
        manifest,
    )
    print(json.dumps({"raw": str(raw_path), "manifest": str(destination)}))


if __name__ == "__main__":
    main()
