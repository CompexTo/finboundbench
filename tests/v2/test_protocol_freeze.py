from __future__ import annotations

import json
from pathlib import Path

from purposebench.utils import sha256_json
from purposebench.v2.protocol_freeze import build_protocol_freeze_manifest


def test_freeze_manifest_hashes_declared_artifacts(tmp_path: Path) -> None:
    audit = {
        "status": "PASSED_WITH_RETAINED_FAILURES",
        "paperScaleComplete": False,
        "provenance": {"platformEvidenceCommit": "platform-commit"},
        "limitations": ["bounded pilot"],
    }
    audit["auditHash"] = sha256_json(audit)
    audit_path = tmp_path / "results/v2/derived/protocol-v2-local-evidence-audit.json"
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    second = tmp_path / "docs/v2/result.md"
    second.parent.mkdir(parents=True)
    second.write_text("result\n", encoding="utf-8")

    manifest = build_protocol_freeze_manifest(
        tmp_path,
        (
            "results/v2/derived/protocol-v2-local-evidence-audit.json",
            "docs/v2/result.md",
        ),
    )

    assert manifest["status"] == "FROZEN_WITH_LIMITATIONS"
    assert manifest["artifactCount"] == 2
    claimed_hash = manifest.pop("manifestHash")
    assert claimed_hash == sha256_json(manifest)
