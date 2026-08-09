"""Repository secret scan for the FinBoundBench release.

Scans the working tree (excluding .git, .venv, build artifacts) and the
tracked file set for credential-like patterns. The report classifies each
finding by pattern and file; it never prints matched values.

Usage: python scripts/scan_secrets.py [--out docs/research/SECRET_SCAN_REPORT.md]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("openrouter_key", re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}")),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai_proj_key", re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret", re.compile(r"(?i)aws_secret_access_key\s*=\s*[^\s]{16,}")),
    ("github_token", re.compile(r"ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("gitlab_token", re.compile(r"glpat-[A-Za-z0-9_-]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("stripe_live", re.compile(r"sk_live_[A-Za-z0-9]{20,}|rk_live_[A-Za-z0-9]{20,}")),
    ("google_api", re.compile(r"AIza[0-9A-Za-z_-]{30,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PGP|DSA) PRIVATE KEY-----")),
    ("generic_bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{20,}")),
    ("auth_basic", re.compile(r"(?i)(api[_-]?key|authorization|password|passwd|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9._~+/-]{16,}")),
]

EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", "node_modules", "tmp", ".eggs"}
EXCLUDE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".tar", ".pyc", ".lock", ".woff", ".woff2", ".ttf", ".eot", ".ico"}


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in EXCLUDE_EXT:
            continue
        if path.stat().st_size > 5_000_000:
            continue
        yield path


def load_exceptions() -> set[tuple[str, str]]:
    """Load (path, pattern) exceptions from SECRET_SCAN_EXCEPTIONS.md.

    The exceptions table is the documented authorization for a release file
    to contain credential-shaped strings (all must be reviewed false
    positives). The scan treats the table as an allowlist, so a documented
    exception does not fail the "tracked files clean" gate.
    """
    path = REPO_ROOT / "docs" / "research" / "SECRET_SCAN_EXCEPTIONS.md"
    if not path.exists():
        return set()
    row = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(\w+)\s*\|")
    exceptions: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = row.match(line)
        if m:
            exceptions.add((m.group(1), m.group(2)))
    return exceptions


def scan_file(path: Path, exceptions: set[tuple[str, str]], rel: str) -> list[dict]:
    findings: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern in PATTERNS:
            if pattern.search(line) and (rel, name) not in exceptions:
                findings.append({"pattern": name, "line": lineno})
                break
    return findings


def scan_tree(exceptions: set[tuple[str, str]]) -> dict:
    per_file: dict[str, list[dict]] = {}
    total = 0
    for path in iter_text_files(REPO_ROOT):
        findings = scan_file(path, exceptions, str(path.relative_to(REPO_ROOT)))
        if findings:
            per_file[str(path.relative_to(REPO_ROOT))] = findings
            total += len(findings)
    return {"total_findings": total, "files": per_file}


def scan_tracked(exceptions: set[tuple[str, str]]) -> dict:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    per_file: dict[str, list[dict]] = {}
    total = 0
    for rel in out:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        if path.suffix.lower() in EXCLUDE_EXT:
            continue
        findings = scan_file(path, exceptions, rel)
        if findings:
            per_file[rel] = findings
            total += len(findings)
    return {"total_findings": total, "files": per_file}


def env_verdict() -> dict:
    env_path = REPO_ROOT / ".env"
    return {
        "exists": env_path.exists(),
        "tracked_in_git": bool(
            subprocess.run(
                ["git", "ls-files", "--error-unmatch", ".env"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            ).returncode == 0
        ),
        "ignored": any(
            line.strip().rstrip("/") == ".env"
            for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="FinBoundBench secret scan")
    parser.add_argument("--out", default=str(REPO_ROOT / "docs/research/SECRET_SCAN_REPORT.md"))
    args = parser.parse_args()

    exceptions = load_exceptions()
    tree = scan_tree(exceptions)
    tracked = scan_tracked(exceptions)
    env = env_verdict()

    lines = [
        "# Secret Scan Report",
        "",
        f"Generated: {json.dumps('2026-08-09')} by `scripts/scan_secrets.py` (regex-based; gitleaks not installed on the build machine).",
        "",
        f"- Working-tree findings (all files): **{tree['total_findings']}** across **{len(tree['files'])}** files.",
        f"- Tracked-in-git findings (what a push would expose): **{tracked['total_findings']}** across **{len(tracked['files'])}** files.",
        f"- `.env` exists: **{env['exists']}**; tracked in git: **{env['tracked_in_git']}**; listed in `.gitignore`: **{env['ignored']}**.",
        "",
        "Findings are classified by pattern name only; matched values are never printed. A",
        "finding means a *credential-shaped string* was detected, not necessarily a live",
        "credential. Review each file listed below before release.",
        "",
    ]

    if tracked["files"]:
        lines.append("## Tracked files with credential-shaped content (must be resolved before push)")
        lines.append("")
        for rel, findings in sorted(tracked["files"].items()):
            patterns = sorted({f["pattern"] for f in findings})
            lines.append(f"- `{rel}` — {len(findings)} finding(s): {', '.join(patterns)}")
        lines.append("")
    else:
        lines.append("## Tracked files: clean")
        lines.append("")

    if tree["files"]:
        extra = {rel for rel in tree["files"] if rel not in tracked["files"]}
        if extra:
            lines.append("## Untracked/ignored files with credential-shaped content (do not add to the release branch)")
            lines.append("")
            for rel in sorted(extra):
                patterns = sorted({f["pattern"] for f in tree["files"][rel]})
                lines.append(f"- `{rel}` — {len(tree['files'][rel])} finding(s): {', '.join(patterns)}")
            lines.append("")
            lines.append("If any of these contain real credentials, they must stay out of the release branch;")
            lines.append("if they are synthetic or false-positive strings (e.g. example keys in docs), add a")
            lines.append("`docs/research/SECRET_SCAN_EXCEPTIONS.md` note before release.")
            lines.append("")

    lines.append("## Method")
    lines.append("")
    lines.append("Patterns: OpenRouter/Anthropic/OpenAI keys, AWS access key ids and secrets, GitHub/GitLab")
    lines.append("tokens, Slack tokens, Stripe live keys, Google API keys, JWTs, PEM private-key blocks,")
    lines.append("generic bearer tokens, and `api_key|password|secret|token = <value>` assignments with")
    lines.append("16+ character values. Scanned: working tree excluding `.git`, `.venv`, caches, `tmp/`,")
    lines.append("binary files; plus the exact tracked file set (`git ls-files`). Values are never echoed.")
    lines.append("")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path}")

    if tracked["files"]:
        print("WARNING: tracked findings present, see report")
        for rel in sorted(tracked["files"]):
            print(f"  tracked: {rel}")
    else:
        print("tracked files clean")


if __name__ == "__main__":
    main()
