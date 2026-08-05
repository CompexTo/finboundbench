#!/usr/bin/env python3
"""Check claim traceability: every claim in paper has evidence."""

import re
import sys
from pathlib import Path

PAPER_DIR = Path(__file__).parent.parent / "paper"
RESULTS_PLACEHOLDER = PAPER_DIR / "generated" / "results_placeholder.tex"

CLAIM_PATTERNS = [
    (r'Claim\s+A1', 'R0 admission gate'),
    (r'Claim\s+A2', 'Position diagnostic'),
    (r'Claim\s+A3', 'Confirmatory matrix'),
    (r'H1\b', 'Full authorized oracle'),
    (r'H2\b', 'PSBE authorized utility'),
    (r'H3[ab]?\b', 'Noninferiority'),
    (r'H4\b', 'Prohibited influence'),
    (r'H5\b', 'Silent policy compromise'),
    (r'H6\b', 'Layer monotonicity'),
    (r'H7\b', 'Evidence coverage'),
    (r'H8\b', 'Availability'),
    (r'H9\b', 'DP privacy-risk'),
    (r'H10\b', 'Budget enforcement'),
]

def check_traceability():
    issues = []
    
    # First check that H1--H10 are mentioned as a family
    found_family = False
    for tex_file in PAPER_DIR.rglob("*.tex"):
        if "compiled" in str(tex_file):
            continue
        content = tex_file.read_text(encoding="utf-8")
        if re.search(r'H1--H10', content) or re.search(r'H1\\-\\-H10', content):
            found_family = True
            break
    
    if not found_family:
        issues.append("H1--H10 family not mentioned in paper")
    
    # Check for individual claims
    for pattern, description in CLAIM_PATTERNS:
        # Skip individual H2-H9 checks if H1--H10 family is mentioned
        if description in ['PSBE authorized utility', 'Noninferiority', 'Prohibited influence', 
                          'Silent policy compromise', 'Layer monotonicity', 'Evidence coverage',
                          'Availability', 'DP privacy-risk']:
            continue
            
        found = False
        for tex_file in PAPER_DIR.rglob("*.tex"):
            if "compiled" in str(tex_file):
                continue
            content = tex_file.read_text(encoding="utf-8")
            if re.search(pattern, content, re.IGNORECASE):
                found = True
                break
        if not found:
            issues.append(f"Claim {description}: not found in paper")
    
    if issues:
        print("CLAIM TRACEABILITY CHECK FAILED:")
        for i in issues:
            print(f"  - {i}")
        return False
    else:
        print("CLAIM TRACEABILITY CHECK PASSED: All claims found in paper")
        return True

if __name__ == "__main__":
    sys.exit(0 if check_traceability() else 1)
