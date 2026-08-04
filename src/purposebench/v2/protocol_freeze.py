"""Hash-manifest construction for a scoped protocol-v2-local freeze."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import git_commit, sha256_file, sha256_json
from purposebench.v2.evidence_audit import verify_self_hash

FREEZE_ARTIFACTS = (
    "configs/v2/protocol-v2-local.yaml",
    "configs/v2/openrouter-phase2.json",
    "configs/v2/openrouter-condition-pilot-consent.json",
    "docs/v2/PROTOCOL_READINESS.md",
    "docs/v2/PHASE2_RESULTS.md",
    "results/v2/derived/protocol-v2-local-evidence-audit.json",
    "results/v2/derived/openrouter-claude-closure.json",
    "results/v2/derived/openrouter-position-diagnostic.json",
    "results/v2/derived/openrouter-reduced-governed-matrix.json",
    "results/v2/derived/openrouter-full-condition-pilot.json",
    "results/v2/raw/privacy/dp-training-phase2-validation.json",
    "results/v2/raw/privacy/privacy-attack-phase2-validation.json",
    "results/v2/raw/platform/local-attack-suite-phase2.json",
    "results/v2/raw/inference/openrouter-frontier-budget.jsonl",
    "results/v2/manifests/hmda-2024-dc-source.json",
    "results/v2/manifests/hmda-2024-dc-transform.json",
    "results/v2/manifests/cfpb-2024-01-dc-source.json",
    "results/v2/manifests/cfpb-2024-01-dc-transform.json",
    "docs/v2/model-manifests/gemma4-31b.json",
    "docs/v2/model-manifests/qwen3-4b.json",
    "docs/v2/model-manifests/openrouter-frontier-2026-08-04.json",
)


def build_protocol_freeze_manifest(
    root: Path,
    artifacts: Sequence[str] = FREEZE_ARTIFACTS,
) -> dict[str, Any]:
    """Bind the audited scoped freeze to exact repository files."""

    root = root.resolve()
    audit_path = root / "results/v2/derived/protocol-v2-local-evidence-audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit_hash = verify_self_hash(audit, "auditHash")
    if (
        audit.get("status") != "PASSED_WITH_RETAINED_FAILURES"
        or audit.get("paperScaleComplete") is not False
    ):
        raise ValueError("protocol freeze requires the bounded phase-two audit")

    seen: set[str] = set()
    inventory: list[dict[str, Any]] = []
    for relative in artifacts:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or relative in seen:
            raise ValueError(f"invalid freeze artifact path: {relative}")
        seen.add(relative)
        resolved = (root / path).resolve()
        if root not in resolved.parents or not resolved.is_file():
            raise ValueError(f"freeze artifact is absent or escaped: {relative}")
        inventory.append(
            {
                "path": path.as_posix(),
                "sha256": sha256_file(resolved),
                "sizeBytes": resolved.stat().st_size,
            }
        )

    manifest: dict[str, Any] = {
        "schemaVersion": "purposebound-finance.protocol-freeze.v2",
        "recordedAt": datetime.now(UTC).isoformat(),
        "status": "FROZEN_WITH_LIMITATIONS",
        "protocolId": "protocol-v2-local",
        "scope": "LOCAL_IMPLEMENTATION_AND_BOUNDED_REMOTE_PILOTS",
        "paperScaleComplete": False,
        "researchCommit": git_commit(root),
        "platformCommit": audit["provenance"]["platformEvidenceCommit"],
        "evidenceAudit": {
            "path": "results/v2/derived/protocol-v2-local-evidence-audit.json",
            "auditHash": audit_hash,
        },
        "artifactCount": len(inventory),
        "artifacts": inventory,
        "changePolicy": (
            "Any material post-freeze change requires a protocol deviation entry "
            "and a new freeze manifest; this manifest remains immutable."
        ),
        "limitations": list(audit["limitations"]),
    }
    manifest["manifestHash"] = sha256_json(manifest)
    return manifest
