#!/usr/bin/env python3
"""Fail if withdrawn test-double metrics reappear in the anonymous paper.

The six values below were computed from deterministic test doubles or invalid
formulas (see docs/v3/METRIC_CORRECTION.md) and were withdrawn on 2026-08-06.
They must not appear in the manuscript until live non-TEE results exist.
"""

import re
import sys
from pathlib import Path

PAPER_DIR = Path(__file__).parent.parent / "paper"

WITHDRAWN_PATTERNS = [
    (r'0\.9341', 'withdrawn AUR value'),
    (r'0\.2000', 'withdrawn UIR value'),
    (r'0\.2426', 'withdrawn SPCR value'),
    (r'1\.0000', 'withdrawn EVC value'),
    (r'0\.9857', 'withdrawn availability value'),
    (r'1\.3116', 'withdrawn overhead value'),
    (r'71\.5\\?%', 'withdrawn attack prevention rate'),
    (r'75\.7\\?%', 'withdrawn attack detection rate'),
    (r'24\.3\\?%', 'withdrawn silent compromise rate'),
    (r'98\.6\\?%', 'withdrawn availability percentage'),
    (r'1\.31\\?x', 'withdrawn overhead multiplier'),
    (r'submission[- ]ready', 'submission-ready language'),
    (r'paper submitted to venue', 'submission language'),
]

EXEMPT_FILES = set()


def check_withdrawn_metrics() -> bool:
    issues = []
    for tex_file in PAPER_DIR.rglob("*.tex"):
        if "compiled" in str(tex_file):
            continue
        if tex_file.name in EXEMPT_FILES:
            continue
        content = tex_file.read_text(encoding="utf-8")
        for pattern, description in WITHDRAWN_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                issues.append(
                    f"{tex_file.name}: {description} found {len(matches)} time(s)"
                )
    if issues:
        print("WITHDRAWN METRICS CHECK FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    print("WITHDRAWN METRICS CHECK PASSED: no withdrawn values in the paper")
    return True


if __name__ == "__main__":
    sys.exit(0 if check_withdrawn_metrics() else 1)
