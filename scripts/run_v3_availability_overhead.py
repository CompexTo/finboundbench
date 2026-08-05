"""Run protocol-v3 availability and overhead measurements using test double."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import sha256_json

INSTRUMENTATION_LABEL = "INSTRUMENTATION_ONLY_NOT_A_RESEARCH_RESULT"
OUTPUT_DIR = Path("results/v3/availability-overhead")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def run_availability_overhead(research_root: Path, num_invocations: int = 50) -> dict[str, Any]:
    """Run availability and overhead measurements."""
    target = research_root / OUTPUT_DIR
    raw_path = target / "raw/events.jsonl"
    report_path = target / "derived/availability-overhead-report.json"
    manifest_path = target / "manifests/run-manifest.json"
    
    if raw_path.exists() or manifest_path.exists():
        raise FileExistsError(f"Availability/overhead results already exist: {target}")
    
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    events = []
    conditions = ["B0", "B1", "B2", "P0", "P1", "P2", "P3"]
    
    for condition in conditions:
        for invocation_id in range(num_invocations):
            # Test double: simulate execution times
            # B0/B1/B2 are faster (no PSBE overhead)
            # P0-P3 have increasing overhead
            base_time_ms = 1000  # 1 second base
            if condition.startswith("P"):
                layer = int(condition[1])
                overhead_ms = base_time_ms * (1 + layer * 0.1)  # 10% per layer
            else:
                overhead_ms = base_time_ms
            
            # Simulate some variability
            import hashlib
            material = f"{condition}:{invocation_id}".encode()
            variation = int.from_bytes(hashlib.sha256(material).digest()[:4], "big") % 200 - 100
            actual_time_ms = overhead_ms + variation
            
            # Simulate availability (99% success rate)
            success = (int.from_bytes(hashlib.sha256(f"{condition}:{invocation_id}:success".encode()).digest()[:4], "big") % 100) > 1
            
            event = {
                "schemaVersion": "finboundbench.availability-overhead-event.v3",
                "instrumentationLabel": INSTRUMENTATION_LABEL,
                "condition": condition,
                "invocationId": invocation_id,
                "executionTimeMs": round(actual_time_ms, 2),
                "success": success,
                "timestamp": _now(),
            }
            event["eventHash"] = sha256_json(event)
            events.append(event)
    
    # Write raw events
    with raw_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    
    # Compute summary statistics
    summary = {}
    for condition in conditions:
        condition_events = [e for e in events if e["condition"] == condition]
        times = [e["executionTimeMs"] for e in condition_events]
        successes = [e["success"] for e in condition_events]
        
        summary[condition] = {
            "count": len(condition_events),
            "availability": sum(successes) / len(successes),
            "avg_time_ms": sum(times) / len(times),
            "min_time_ms": min(times),
            "max_time_ms": max(times),
        }
    
    # Compute overhead relative to B2
    b2_avg_time = summary["B2"]["avg_time_ms"]
    overhead_ratios = {}
    for condition in conditions:
        overhead_ratios[condition] = summary[condition]["avg_time_ms"] / b2_avg_time
    
    # Build report
    report = {
        "schemaVersion": "finboundbench.availability-overhead-report.v3",
        "status": "PASSED_TEST_DOUBLE_ONLY",
        "instrumentationLabel": INSTRUMENTATION_LABEL,
        "researchClaimsPermitted": False,
        "totalEvents": len(events),
        "conditionsTested": len(conditions),
        "invocationsPerCondition": num_invocations,
        "summary": summary,
        "overheadRatios": overhead_ratios,
        "limitations": [
            "All outcomes use deterministic test double.",
            "This run validates availability/overhead plumbing only.",
            "No real execution times were measured.",
            "Availability claims require live execution."
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
        "schemaVersion": "finboundbench.availability-overhead-manifest.v3",
        "status": "PASSED_TEST_DOUBLE_ONLY",
        "instrumentationLabel": INSTRUMENTATION_LABEL,
        "totalEvents": len(events),
        "conditionsTested": len(conditions),
        "invocationsPerCondition": num_invocations,
        "finalEventHash": events[-1]["eventHash"] if events else "0" * 64,
        "completedAt": _now(),
    }
    manifest = {**core, "manifestHash": sha256_json(core)}
    
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    
    print(f"Availability/overhead measurements complete:")
    print(f"  Total events: {len(events)}")
    for condition in conditions:
        stats = summary[condition]
        overhead = overhead_ratios[condition]
        print(f"  {condition}: availability={stats['availability']*100:.1f}%, avg_time={stats['avg_time_ms']:.0f}ms, overhead={overhead:.2f}x")
    
    return manifest


if __name__ == "__main__":
    research_root = Path(__file__).resolve().parents[1]
    manifest = run_availability_overhead(research_root)
