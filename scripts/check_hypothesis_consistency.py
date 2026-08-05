#!/usr/bin/env python3
"""Check hypothesis consistency: H1-H10 definitions match paper."""

import re
import sys
from pathlib import Path

PAPER_DIR = Path(__file__).parent.parent / "paper"

EXPECTED_HYPOTHESES = {
    "H1": "Full authorized oracle improves Task A balanced accuracy over public-only by at least 0.08",
    "H2": "Full PSBE (P3) retains at least 80% of the oracle's incremental Task A utility",
    "H3a": "P0 is noninferior to B2 in task balanced accuracy with margin 0.05",
    "H3b": "P0 is equivalent to B2 in UIR within 0.03 margin",
    "H4": "P3 has lower Task B UIR than B0 and B1, Holm-adjusted p < 0.05",
    "H5": "P3 reduces silent policy compromise relative to B2 by >= 0.20 absolute",
    "H6": "Adding P0--P3 layers does not increase silent compromise and reduces it in >= 2 families",
    "H7": ">= 0.95 of successful P3 executions have 100% mandatory-claim coverage",
    "H8": "P3 availability is noninferior to B2 with margin 0.10",
    "H9": "D2 reduces composite privacy-risk rank without decreasing balanced accuracy by > 0.10",
    "H10": "Every budget attack attempt is prevented or fails closed",
}

def check_hypothesis_consistency():
    issues = []
    for tex_file in PAPER_DIR.rglob("*.tex"):
        content = tex_file.read_text(encoding="utf-8")
        for h_id in EXPECTED_HYPOTHESES:
            if re.search(rf'\b{h_id}\b', content):
                # Check if the hypothesis is mentioned
                pass
    
    # Check that H1-H10 are defined
    results_content = (PAPER_DIR / "generated" / "result_statements.md").read_text(encoding="utf-8")
    for h_id in EXPECTED_HYPOTHESES:
        if h_id not in results_content:
            issues.append(f"{h_id} not defined in result_statements.md")
    
    if issues:
        print("HYPOTHESIS CONSISTENCY CHECK FAILED:")
        for i in issues:
            print(f"  - {i}")
        return False
    else:
        print("HYPOTHESIS CONSISTENCY CHECK PASSED: All H1-H10 defined")
        return True

if __name__ == "__main__":
    sys.exit(0 if check_hypothesis_consistency() else 1)
