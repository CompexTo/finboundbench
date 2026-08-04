"""Build the sealed phase-two evidence audit after local validation."""

from __future__ import annotations

import argparse
from pathlib import Path

from purposebench.v2.claude_compatibility import _secret_scan
from purposebench.v2.evidence_audit import build_phase2_evidence_audit
from purposebench.v2.pilots import write_new_v2_artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/v2/derived/protocol-v2-local-evidence-audit.json"),
    )
    args = parser.parse_args()
    benchmark_root = Path(__file__).resolve().parents[1]
    platform_root = args.platform_root.resolve()
    secret_scan = _secret_scan(benchmark_root, platform_root)
    audit = build_phase2_evidence_audit(
        benchmark_root,
        platform_root,
        secret_scan,
    )
    destination = write_new_v2_artifact(benchmark_root, args.output, audit)
    print(f"{audit['status']} {destination}")


if __name__ == "__main__":
    main()
