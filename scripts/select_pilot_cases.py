from pathlib import Path

from purposebench.dataset.select import select_stratified_cases

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    manifest = select_stratified_cases(
        ROOT / "data" / "generated" / "cases.jsonl",
        ROOT / "data" / "generated" / "pilot_40.jsonl",
        ROOT / "results" / "manifests" / "pilot_40_manifest.json",
        cases_per_workflow=10,
    )
    print(
        f"Selected {manifest['records']} records ({manifest['pairs']} pairs); "
        f"SHA-256 {manifest['subset_sha256']}"
    )
