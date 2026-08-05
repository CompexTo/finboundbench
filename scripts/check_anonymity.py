#!/usr/bin/env python3
"""Check anonymity: no Compex, no author names, no affiliations."""

import re
import sys
from pathlib import Path

ANONYMOUS_PATTERNS = [
    r'\bCompex\b',
    r'\bAmir\s+M\.\s+Farhang\b',
    r'\bIftekhar\s+Anwar\b',
    r'\bLuca\s+Pulvirenti\b',
    r'\bgetcompex\.com\b',
    r'\bI3P\b',
    r'\bPolitecnico\s+di\s+Torino\b',
]

PAPER_DIR = Path(__file__).parent.parent / "paper"

def check_anonymity():
    violations = []
    for tex_file in PAPER_DIR.rglob("*.tex"):
        content = tex_file.read_text(encoding="utf-8")
        for pattern in ANONYMOUS_PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                violations.append(f"{tex_file.name}: {pattern} found {len(matches)} times")
    
    if violations:
        print("ANONYMITY CHECK FAILED:")
        for v in violations:
            print(f"  - {v}")
        return False
    else:
        print("ANONYMITY CHECK PASSED: No author/affiliation leaks found")
        return True

if __name__ == "__main__":
    sys.exit(0 if check_anonymity() else 1)
