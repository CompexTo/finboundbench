from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(root: Path | None = None) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "uncommitted"


def git_provenance(root: Path) -> dict[str, Any]:
    """Return reproducibility metadata without copying source diffs into results."""
    try:
        commit = git_commit(root)
        diff = subprocess.check_output(
            ["git", "diff", "--binary", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
        )
        return {
            "commit": commit,
            "tracked_tree_dirty": bool(diff),
            "tracked_diff_sha256": hashlib.sha256(diff).hexdigest() if diff else None,
        }
    except (OSError, subprocess.CalledProcessError):
        return {
            "commit": "unavailable",
            "tracked_tree_dirty": None,
            "tracked_diff_sha256": None,
        }


def docker_image_provenance(image: str) -> dict[str, Any]:
    """Resolve a local container tag to its immutable image identifier."""
    try:
        output = subprocess.check_output(
            ["docker", "image", "inspect", image],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        inspected = json.loads(output)[0]
        return {
            "reference": image,
            "image_id": inspected.get("Id"),
            "repo_digests": inspected.get("RepoDigests") or [],
            "created": inspected.get("Created"),
            "os": inspected.get("Os"),
            "architecture": inspected.get("Architecture"),
        }
    except (OSError, subprocess.CalledProcessError, IndexError, KeyError, json.JSONDecodeError):
        return {
            "reference": image,
            "image_id": None,
            "repo_digests": [],
            "error": "local image metadata unavailable",
        }


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows
