"""Run protocol-v3 evidence verification using test double oracle."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import sha256_json

INSTRUMENTATION_LABEL = "INSTRUMENTATION_ONLY_NOT_A_RESEARCH_RESULT"
OUTPUT_DIR = Path("results/v3/evidence-verification")

MANDATORY_CLAIMS = [
    "contract_integrity",
    "projection_integrity",
    "model_integrity",
    "capability_integrity",
    "privacy_integrity",
    "release_integrity",
    "evidence_integrity",
]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def run_evidence_verification(research_root: Path, num_executions: int = 20) -> dict[str, Any]:
    """Run evidence verification across successful P3 executions."""
    target = research_root / OUTPUT_DIR
    raw_path = target / "raw/events.jsonl"
    report_path = target / "derived/evidence-report.json"
    manifest_path = target / "manifests/run-manifest.json"
    
    if raw_path.exists() or manifest_path.exists():
        raise FileExistsError(f"Evidence verification results already exist: {target}")
    
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    events = []
    full_coverage_count = 0
    
    for execution_id in range(num_executions):
        # Simulate evidence bundle verification
        verified_claims = []
        for claim in MANDATORY_CLAIMS:
            # Test double: all claims pass
            verified_claims.append({
                "claim": claim,
                "status": "VERIFIED",
                "hash": sha256_json({"claim": claim, "execution_id": execution_id}),
            })
        
        coverage = len(verified_claims) / len(MANDATORY_CLAIMS)
        if coverage == 1.0:
            full_coverage_count += 1
        
        event = {
            "schemaVersion": "finboundbench.evidence-event.v3",
            "instrumentationLabel": INSTRUMENTATION_LABEL,
            "executionId": execution_id,
            "mandatoryClaimCount": len(MANDATORY_CLAIMS),
            "verifiedClaimCount": len(verified_claims),
            "coverage": coverage,
            "fullCoverage": coverage == 1.0,
            "timestamp": _now(),
        }
        event["eventHash"] = sha256_json(event)
        events.append(event)
    
    # Write raw events
    with raw_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    
    # Build report
    report = {
        "schemaVersion": "finboundbench.evidence-report.v3",
        "status": "PASSED_TEST_DOUBLE_ONLY",
        "instrumentationLabel": INSTRUMENTATION_LABEL,
        "researchClaimsPermitted": False,
        "totalExecutions": num_executions,
        "mandatoryClaimsPerExecution": len(MANDATORY_CLAIMS),
        "fullCoverageCount": full_coverage_count,
        "fullCoverageRate": full_coverage_count / num_executions,
        "limitations": [
            "All evidence outcomes use deterministic test double.",
            "This run validates evidence verification plumbing only.",
            "No real evidence bundle was verified.",
            "Evidence claims require live evidence verification."
        ],
        "reportHash": "",
    }
    report_material = dict(report)
    report_material.pop("reportHash")
    report["reportHash"] = sha256_json(report_material)
    
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    
    # Build manifest
    core = {
        "schemaVersion": "finboundbench.evidence-verification-manifest.v3",
        "status": "PASSED_TEST_DOUBLE_ONLY",
        "instrumentationLabel": INSTRUMENTATION_LABEL,
        "totalEvents": len(events),
        "totalExecutions": num_executions,
        "fullCoverageRate": full_coverage_count / num_executions,
        "finalEventHash": events[-1]["eventHash"] if events else "0" * 64,
        "completedAt": _now(),
    }
    manifest = {**core, "manifestHash": sha256_json(core)}
    
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    
    print(f"Evidence verification complete:")
    print(f"  Total executions: {num_executions}")
    print(f"  Full coverage: {full_coverage_count}/{num_executions} ({full_coverage_count/num_executions*100:.1f}%)")
    
    return manifest


if __name__ == "__main__":
    research_root = Path(__file__).resolve().parents[1]
    manifest = run_evidence_verification(research_root)
