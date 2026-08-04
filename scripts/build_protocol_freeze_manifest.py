"""Create the immutable protocol-v2-local scoped-freeze manifest."""

from __future__ import annotations

from pathlib import Path

from purposebench.v2.pilots import write_new_v2_artifact
from purposebench.v2.protocol_freeze import build_protocol_freeze_manifest


def main() -> None:
    benchmark_root = Path(__file__).resolve().parents[1]
    manifest = build_protocol_freeze_manifest(benchmark_root)
    destination = write_new_v2_artifact(
        benchmark_root,
        Path("results/v2/manifests/protocol-v2-local-freeze.json"),
        manifest,
    )
    print(f"{manifest['status']} {destination}")


if __name__ == "__main__":
    main()
