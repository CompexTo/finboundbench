"""Run protocol-v3 attack suite using test double oracle."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import sha256_json
from purposebench.v3.attacks import ATTACK_REGISTRY, execute_test_double_attack

INSTRUMENTATION_LABEL = "INSTRUMENTATION_ONLY_NOT_A_RESEARCH_RESULT"
OUTPUT_DIR = Path("results/v3/attack-suite")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def run_attack_suite(research_root: Path) -> dict[str, Any]:
    """Run all 57 attacks across applicable conditions."""
    target = research_root / OUTPUT_DIR
    raw_path = target / "raw/events.jsonl"
    report_path = target / "derived/attack-report.json"
    manifest_path = target / "manifests/run-manifest.json"
    
    if raw_path.exists() or manifest_path.exists():
        raise FileExistsError(f"Attack suite results already exist: {target}")
    
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    events = []
    outcome_counts: dict[str, int] = {}
    family_counts: dict[str, dict[str, int]] = {}
    
    for attack in ATTACK_REGISTRY:
        for condition in attack.applicable_conditions:
            outcome = execute_test_double_attack(attack, condition)
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
            
            if attack.family not in family_counts:
                family_counts[attack.family] = {}
            family_counts[attack.family][outcome] = family_counts[attack.family].get(outcome, 0) + 1
            
            event = {
                "schemaVersion": "finboundbench.attack-event.v3",
                "instrumentationLabel": INSTRUMENTATION_LABEL,
                "attackId": attack.attack_id,
                "family": attack.family,
                "requiredControl": attack.required_control,
                "condition": condition,
                "outcome": outcome,
                "oracle": "DETERMINISTIC_TEST_DOUBLE",
                "timestamp": _now(),
            }
            event["eventHash"] = sha256_json(event)
            events.append(event)
    
    # Write raw events
    with raw_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    
    # Build report
    total_attacks = len(events)
    prevented = outcome_counts.get("PREVENTED", 0)
    failed_closed = outcome_counts.get("FAILED_CLOSED", 0)
    detected = outcome_counts.get("SUCCEEDED_DETECTED", 0)
    silent = outcome_counts.get("SILENT_COMPROMISE", 0)
    inconclusive = outcome_counts.get("INCONCLUSIVE", 0)
    
    report = {
        "schemaVersion": "finboundbench.attack-report.v3",
        "status": "PASSED_TEST_DOUBLE_ONLY",
        "instrumentationLabel": INSTRUMENTATION_LABEL,
        "researchClaimsPermitted": False,
        "totalAttacks": total_attacks,
        "registeredAttackIds": len(ATTACK_REGISTRY),
        "outcomeCounts": outcome_counts,
        "preventionRate": prevented / total_attacks if total_attacks > 0 else 0,
        "failClosedRate": failed_closed / total_attacks if total_attacks > 0 else 0,
        "detectionRate": (prevented + failed_closed + detected) / total_attacks if total_attacks > 0 else 0,
        "silentCompromiseRate": silent / total_attacks if total_attacks > 0 else 0,
        "byFamily": family_counts,
        "limitations": [
            "All attacks use deterministic test double oracle.",
            "This run validates attack classification plumbing only.",
            "No real attack was executed against the runtime.",
            "Security claims require live attack execution."
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
        "schemaVersion": "finboundbench.attack-suite-manifest.v3",
        "status": "PASSED_TEST_DOUBLE_ONLY",
        "instrumentationLabel": INSTRUMENTATION_LABEL,
        "totalEvents": len(events),
        "totalAttacks": total_attacks,
        "outcomeCounts": outcome_counts,
        "finalEventHash": events[-1]["eventHash"] if events else "0" * 64,
        "completedAt": _now(),
    }
    manifest = {**core, "manifestHash": sha256_json(core)}
    
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    
    print(f"Attack suite complete:")
    print(f"  Total attacks: {total_attacks}")
    print(f"  PREVENTED: {prevented} ({prevented/total_attacks*100:.1f}%)")
    print(f"  FAILED_CLOSED: {failed_closed} ({failed_closed/total_attacks*100:.1f}%)")
    print(f"  SUCCEEDED_DETECTED: {detected} ({detected/total_attacks*100:.1f}%)")
    print(f"  SILENT_COMPROMISE: {silent} ({silent/total_attacks*100:.1f}%)")
    print(f"  INCONCLUSIVE: {inconclusive} ({inconclusive/total_attacks*100:.1f}%)")
    print(f"  Detection rate: {(prevented + failed_closed + detected)/total_attacks*100:.1f}%")
    
    return manifest


if __name__ == "__main__":
    research_root = Path(__file__).resolve().parents[1]
    manifest = run_attack_suite(research_root)
