#!/usr/bin/env python3
"""Check unsupported language: no causal claims about providers."""

import re
import sys
from pathlib import Path

PAPER_DIR = Path(__file__).parent.parent / "paper"

UNSUPPORTED_PATTERNS = [
    (r'because.*release.*denied', 'Causal explanation for release denial'),
    (r'therefore.*release.*denied', 'Causal explanation for release denial'),
    (r'thus.*release.*denied', 'Causal explanation for release denial'),
    (r'caused.*release.*denied', 'Causal explanation for release denial'),
    (r'Provider.*refuse', 'Unsupported provider behavior claim'),
    (r'Provider.*reject', 'Unsupported provider behavior claim'),
    (r'publicly\s+auditable', 'Unsupported public auditability claim'),
    (r'supplementary\s+registry', 'Unsupported supplementary registry claim'),
]

def check_unsupported_language():
    issues = []
    for tex_file in PAPER_DIR.rglob("*.tex"):
        if "compiled" in str(tex_file):
            continue  # Skip compiled directory
        content = tex_file.read_text(encoding="utf-8")
        for pattern, description in UNSUPPORTED_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                issues.append(f"{tex_file.name}: {description} found {len(matches)} times")
    
    if issues:
        print("UNSUPPORTED LANGUAGE CHECK FAILED:")
        for i in issues:
            print(f"  - {i}")
        return False
    else:
        print("UNSUPPORTED LANGUAGE CHECK PASSED: No unsupported claims found")
        return True

if __name__ == "__main__":
    sys.exit(0 if check_unsupported_language() else 1)
