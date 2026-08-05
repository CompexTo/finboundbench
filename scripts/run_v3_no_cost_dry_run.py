"""Execute the frozen no-cost non-TEE protocol-v3 instrumentation run."""

from pathlib import Path

from purposebench.v3.dry_run import run_no_cost_dry_run

if __name__ == "__main__":
    research_root = Path(__file__).resolve().parents[1]
    platform_root = research_root.parents[1]
    manifest = run_no_cost_dry_run(research_root, platform_root)
    print(
        "PASSED_INSTRUMENTATION_ONLY "
        f"events={manifest['eventCounts']['total']} "
        f"manifest={manifest['manifestHash']}"
    )
