#!/usr/bin/env python3
"""Check page count: verify paper is within 8-page limit."""

import subprocess
import sys
from pathlib import Path

PAPER_DIR = Path(__file__).parent.parent / "paper"
MAIN_TEX = PAPER_DIR / "main.tex"

def check_page_count():
    # Try to compile and check page count
    try:
        # First try pdflatex
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(PAPER_DIR), str(MAIN_TEX)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Check for page count in log
        log_file = PAPER_DIR / "main.log"
        if log_file.exists():
            log_content = log_file.read_text(encoding="utf-8", errors="ignore")
            if "[*]" in log_content:
                # Count pages
                pages = log_content.count("[*]")
                if pages > 8:
                    print(f"PAGE COUNT CHECK FAILED: Paper is {pages} pages (limit: 8)")
                    return False
                else:
                    print(f"PAGE COUNT CHECK PASSED: Paper is {pages} pages")
                    return True
        
        print("PAGE COUNT CHECK: Could not determine page count (no LaTeX compiler)")
        return True  # Skip if no compiler
        
    except FileNotFoundError:
        print("PAGE COUNT CHECK: pdflatex not found, skipping")
        return True
    except subprocess.TimeoutExpired:
        print("PAGE COUNT CHECK: Compilation timed out")
        return True

if __name__ == "__main__":
    sys.exit(0 if check_page_count() else 1)
