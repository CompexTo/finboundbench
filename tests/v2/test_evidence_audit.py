from __future__ import annotations

from pathlib import Path

from purposebench.utils import sha256_json
from purposebench.v2.evidence_audit import build_phase2_evidence_audit

ROOT = Path(__file__).parents[2]
PLATFORM_ROOT = ROOT.parents[1]


def _passing_secret_scan() -> dict[str, object]:
    return {
        "credentialReference": {
            "provider": "LOCAL_ENV_REFERENCE",
            "reference": "OPENROUTER_API_KEY",
        },
        "trackedSecretValueHits": 0,
        "gitHistorySecretValueHits": 0,
        "keyValueRecorded": False,
        "keyValueHashed": False,
    }


def test_phase2_evidence_audit_validates_committed_evidence() -> None:
    audit = build_phase2_evidence_audit(ROOT, PLATFORM_ROOT, _passing_secret_scan())

    assert audit["status"] == "PASSED_WITH_RETAINED_FAILURES"
    assert audit["paperScaleComplete"] is False
    assert audit["budget"]["globalCommittedEur"] == 9.01262918
    assert audit["budget"]["additionalRemainingEur"] == 3.88976466
    assert audit["remoteExecution"]["fallbacks"] == 0
    assert audit["remoteExecution"]["automaticRetries"] == 0
    assert audit["platformValidation"]["attackCount"] == 17
    claimed_hash = audit.pop("auditHash")
    assert claimed_hash == sha256_json(audit)
