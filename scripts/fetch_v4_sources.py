"""Fetch the public source datasets used by FinBoundBench v4.

Downloads the exact public records referenced by the v4 signal design:

- HMDA 2024, District of Columbia (mortgage application records)
- CFPB Consumer Complaints, January 2024, District of Columbia

Outputs go to data/v4/sources/ (gitignored; no raw CSVs are committed).
The FinBoundBench pair files (data/v4/v4_*/*.jsonl) are self-contained and
do NOT depend on these downloads for reproducibility — this script exists so
the provenance of the public features can be re-traced.

Usage:
    python scripts/fetch_v4_sources.py            # download + extract
    python scripts/fetch_v4_sources.py --check    # verify extraction only
"""

import argparse
import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "v4" / "sources"

# Public URLs. The HMDA snapshot endpoint serves a CSV inside a zip; the CFPB
# endpoint serves CSV directly.
SOURCES = {
    "hmda_dc_2024.csv": (
        "https://ffiec.cfpb.gov/data-publication/snapshot-national-loan-level-dataset/2024",
        "hmda_2024_dc.csv.zip",
        ["hmda_2024_dc.csv"],
    ),
    "cfpb_complaints_2024_01_dc.csv": (
        "https://files.consumerfinance.gov/ccdb/complaints.csv.zip",
        "complaints.csv.zip",
        ["complaints.csv"],
    ),
}

# Expected content hashes (SHA-256) for the extracted files, when known.
# Populate after the first successful fetch and verify with --check.
EXPECTED = {}


def fetch(name: str, url: str, archive: str, members: list[str]) -> None:
    dest = OUT_DIR / archive
    if dest.exists():
        print(f"[skip] {archive} already present")
    else:
        print(f"[fetch] {url}")
        urllib.request.urlretrieve(url, dest)
    with zipfile.ZipFile(dest) as z:
        z.extractall(OUT_DIR)
    for member in members:
        p = OUT_DIR / member
        if not p.exists():
            sys.exit(f"missing expected member {member} in {archive}")
        print(f"[ok] {member} ({p.stat().st_size / 1e6:.1f} MB)")


def check() -> int:
    bad = 0
    for name, (_, archive, members) in SOURCES.items():
        for member in members:
            p = OUT_DIR / member
            if not p.exists():
                print(f"[MISSING] {member}")
                bad += 1
                continue
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            want = EXPECTED.get(member)
            if want and h != want:
                print(f"[HASH MISMATCH] {member}: {h[:16]} (expected {want[:16]})")
                bad += 1
            else:
                print(f"[ok] {member} sha256={h[:16]}")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify extraction only")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.check:
        return check()
    for name, (url, archive, members) in SOURCES.items():
        fetch(name, url, archive, members)
    print("[done] run with --check to verify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
