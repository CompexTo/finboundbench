# Secret Scan Report

Generated: "2026-08-09" by `scripts/scan_secrets.py` (regex-based; gitleaks not installed on the build machine).

- Working-tree findings (all files): **1** across **1** files.
- Tracked-in-git findings (what a push would expose): **0** across **0** files.
- `.env` exists: **True**; tracked in git: **False**; listed in `.gitignore`: **True**.

Findings are classified by pattern name only; matched values are never printed. A
finding means a *credential-shaped string* was detected, not necessarily a live
credential. Review each file listed below before release.

## Tracked files: clean

## Untracked/ignored files with credential-shaped content (do not add to the release branch)

- `src\purposebench\v4\eligibility_runner.py` — 1 finding(s): auth_basic

If any of these contain real credentials, they must stay out of the release branch;
if they are synthetic or false-positive strings (e.g. example keys in docs), add a
`docs/research/SECRET_SCAN_EXCEPTIONS.md` note before release.

## Method

Patterns: OpenRouter/Anthropic/OpenAI keys, AWS access key ids and secrets, GitHub/GitLab
tokens, Slack tokens, Stripe live keys, Google API keys, JWTs, PEM private-key blocks,
generic bearer tokens, and `api_key|password|secret|token = <value>` assignments with
16+ character values. Scanned: working tree excluding `.git`, `.venv`, caches, `tmp/`,
binary files; plus the exact tracked file set (`git ls-files`). Values are never echoed.
