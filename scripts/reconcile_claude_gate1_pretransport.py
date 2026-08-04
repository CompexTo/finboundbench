"""Append proof that the first phase-two Gate 1 failure occurred before transport."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from purposebench.utils import (
    append_jsonl,
    git_commit,
    read_jsonl,
    sha256_file,
    sha256_json,
    sha256_text,
)
from purposebench.v2.claude_compatibility import AUTHORIZATION_ID, BUDGET_CATEGORY
from purposebench.v2.phase_budget import reconcile_pretransport_failure
from purposebench.v2.pilots import write_new_v2_artifact


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    platform_root = Path(os.environ["COMPEX_PLATFORM_ROOT"]).resolve()
    partial = root / "results/v2/raw/inference/openrouter-phase2-claude-gate1.jsonl.partial"
    rows = read_jsonl(partial)
    if len(rows) != 1 or rows[0].get("status") != "failed":
        raise ValueError("Gate 1 pre-transport failure evidence is not in its original state")
    failure = rows[0]
    original_hash = sha256_file(partial)
    gate0 = json.loads(
        (root / "results/v2/manifests/openrouter-claude-gate0-20260805.json").read_text(
            encoding="utf-8"
        )
    )
    buggy_commit = gate0["researchCommit"]
    buggy_bridge = subprocess.run(
        ["git", "show", f"{buggy_commit}:scripts/governed_openrouter_bridge.cjs"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    model_manifest = json.loads(
        (root / "results/v2/manifests/openrouter-claude-model-20260804T223732Z.json").read_text(
            encoding="utf-8"
        )
    )
    current_bridge_path = root / "scripts/governed_openrouter_bridge.cjs"
    current_bridge = current_bridge_path.read_text(encoding="utf-8")
    if (
        "endpoint: manifest.endpoint" not in buggy_bridge
        or "endpoint" in model_manifest
        or "      endpoint," not in current_bridge
    ):
        raise ValueError("Gate 1 pre-transport endpoint defect cannot be proven")
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    probe = subprocess.run(
        [sys.executable, str(root / "scripts/probe_openrouter_phase2_contract.py")],
        cwd=root,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
        check=False,
    )
    if probe.returncode != 0:
        raise RuntimeError("Corrected fake-transport contract probe did not pass")
    probe_result = json.loads(probe.stdout)
    if probe_result.get("externalProviderCalls") != 0 or probe_result.get("status") != "PASSED":
        raise ValueError("Corrected fake-transport proof is invalid")
    correction = {
        "schemaVersion": "purposebound-finance.evidence-correction.v2",
        "recordType": "evidence_correction",
        "recordedAt": datetime.now(UTC).isoformat(),
        "originalEvidenceId": failure["evidenceId"],
        "originalArtifactSha256": original_hash,
        "classification": "PRE_TRANSPORT_LOCAL_VALIDATION_FAILURE",
        "correctedProviderCalls": 0,
        "correctedRetryCount": 0,
        "correctedConservativeDebitEur": 0.0,
        "reason": "V3_MANIFEST_ENDPOINT_NORMALIZATION_NOT_PROPAGATED",
        "buggyBridgeCommit": buggy_commit,
        "buggyBridgeSha256": sha256_text(buggy_bridge),
        "correctedBridgeCommit": git_commit(root),
        "correctedBridgeSha256": sha256_file(current_bridge_path),
        "correctedContractProbe": probe_result,
        "originalFailureRecordUnchanged": True,
    }
    append_jsonl(partial, correction)
    corrected_artifact_hash = sha256_file(partial)
    ledger_path = root / "results/v2/raw/inference/openrouter-frontier-budget.jsonl"
    global_committed, category_committed = reconcile_pretransport_failure(
        ledger_path,
        reservation_id=failure["budget"]["reservationId"],
        model_id=failure["contractMaterial"]["modelId"],
        phase="claude_gate_1",
        category=BUDGET_CATEGORY,
        authorization_id=AUTHORIZATION_ID,
        evidence_artifact=partial.relative_to(root).as_posix(),
        evidence_artifact_sha256=corrected_artifact_hash,
    )
    ledger_rows = read_jsonl(ledger_path)
    reconciliation = {
        "schemaVersion": "purposebound-finance.pretransport-reconciliation.v2",
        "status": "RECONCILED",
        "failureArtifact": partial.relative_to(root).as_posix(),
        "originalFailureArtifactSha256": original_hash,
        "correctedFailureArtifactSha256": corrected_artifact_hash,
        "originalEvidenceId": failure["evidenceId"],
        "correctedProviderCalls": 0,
        "correctedConservativeDebitEur": 0.0,
        "budgetReservationId": failure["budget"]["reservationId"],
        "budgetLedgerPrefixRecordCount": len(ledger_rows),
        "budgetLedgerPrefixHash": sha256_json(ledger_rows),
        "globalCommittedEur": global_committed,
        "categoryCommittedEur": category_committed,
        "buggyBridgeCommit": buggy_commit,
        "buggyBridgeSha256": correction["buggyBridgeSha256"],
        "correctedBridgeCommit": correction["correctedBridgeCommit"],
        "correctedBridgeSha256": correction["correctedBridgeSha256"],
        "correctedContractProbe": probe_result,
        "providerCallOccurred": False,
        "originalEvidenceRetainedAppendOnly": True,
    }
    destination = write_new_v2_artifact(
        root,
        Path("results/v2/manifests/openrouter-phase2-claude-gate1-pretransport-reconciliation.json"),
        reconciliation,
    )
    print(json.dumps({"artifact": destination.relative_to(root).as_posix(), **probe_result}))


if __name__ == "__main__":
    main()
