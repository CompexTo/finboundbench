"""Run protocol-v3 statistical analysis and compute final metrics."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from purposebench.utils import sha256_json

INSTRUMENTATION_LABEL = "INSTRUMENTATION_ONLY_NOT_A_RESEARCH_RESULT"
OUTPUT_DIR = Path("results/v3/statistical-analysis")


def run_statistical_analysis(research_root: Path) -> dict[str, Any]:
    """Compute all metrics from existing experimental data."""
    target = research_root / OUTPUT_DIR
    report_path = target / "derived/statistical-report.json"
    manifest_path = target / "manifests/run-manifest.json"
    
    if report_path.exists() or manifest_path.exists():
        raise FileExistsError(f"Statistical analysis results already exist: {target}")
    
    target.mkdir(parents=True, exist_ok=True)
    
    # Load confirmatory run results
    confirmatory_path = research_root / "results/v3/confirmatory-reduced/raw/events.jsonl"
    if confirmatory_path.exists():
        confirmatory_events = [json.loads(line) for line in confirmatory_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        confirmatory_events = []
    
    # Load attack suite results
    attack_path = research_root / "results/v3/attack-suite/raw/events.jsonl"
    if attack_path.exists():
        attack_events = [json.loads(line) for line in attack_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        attack_events = []
    
    # Load DP experiment results
    dp_path = research_root / "results/v3/dp-experiments/raw/events.jsonl"
    if dp_path.exists():
        dp_events = [json.loads(line) for line in dp_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        dp_events = []
    
    # Load evidence verification results
    evidence_path = research_root / "results/v3/evidence-verification/raw/events.jsonl"
    if evidence_path.exists():
        evidence_events = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        evidence_events = []
    
    # Load availability/overhead results
    availability_path = research_root / "results/v3/availability-overhead/raw/events.jsonl"
    if availability_path.exists():
        availability_events = [json.loads(line) for line in availability_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        availability_events = []
    
    # Compute metrics
    metrics = {}
    
    # AUR (Authorized Utility Retention)
    # From confirmatory run: compare B0 vs P3 pass rates
    b0_events = [e for e in confirmatory_events if e.get("conditionId") == "B0"]
    p3_events = [e for e in confirmatory_events if e.get("conditionId") == "P3"]
    
    b0_pass_rate = sum(1 for e in b0_events if e.get("status") == "PASSED") / len(b0_events) if b0_events else 0
    p3_pass_rate = sum(1 for e in p3_events if e.get("status") == "PASSED") / len(p3_events) if p3_events else 0
    
    # AUR = p3_pass_rate / b0_pass_rate (simplified)
    aur = p3_pass_rate / b0_pass_rate if b0_pass_rate > 0 else 0
    
    metrics["AUR"] = {
        "value": round(aur, 4),
        "description": "Authorized Utility Retention",
        "b0_pass_rate": round(b0_pass_rate, 4),
        "p3_pass_rate": round(p3_pass_rate, 4),
    }
    
    # UIR (Unauthorized Influence Rate)
    # From confirmatory run: release denied rate
    total_events = len(confirmatory_events)
    release_denied = sum(1 for e in confirmatory_events if e.get("status") == "RELEASE_DENIED")
    uir = release_denied / total_events if total_events > 0 else 0
    
    metrics["UIR"] = {
        "value": round(uir, 4),
        "description": "Unauthorized Influence Rate",
        "release_denied": release_denied,
        "total": total_events,
    }
    
    # SPCR (Silent Policy Compromise Rate)
    # From attack suite: silent compromise rate
    attack_total = len(attack_events)
    silent_compromise = sum(1 for e in attack_events if e.get("outcome") == "SILENT_COMPROMISE")
    spcr = silent_compromise / attack_total if attack_total > 0 else 0
    
    metrics["SPCR"] = {
        "value": round(spcr, 4),
        "description": "Silent Policy Compromise Rate",
        "silent_compromise": silent_compromise,
        "total": attack_total,
    }
    
    # EVC (Evidence Verification Coverage)
    evidence_total = len(evidence_events)
    full_coverage = sum(1 for e in evidence_events if e.get("fullCoverage"))
    evc = full_coverage / evidence_total if evidence_total > 0 else 0
    
    metrics["EVC"] = {
        "value": round(evc, 4),
        "description": "Evidence Verification Coverage",
        "full_coverage": full_coverage,
        "total": evidence_total,
    }
    
    # Availability
    availability_total = len(availability_events)
    successes = sum(1 for e in availability_events if e.get("success"))
    availability = successes / availability_total if availability_total > 0 else 0
    
    metrics["availability"] = {
        "value": round(availability, 4),
        "description": "Availability",
        "successes": successes,
        "total": availability_total,
    }
    
    # Overhead
    # From availability/overhead measurements
    b2_times = [e["executionTimeMs"] for e in availability_events if e.get("condition") == "B2"]
    p3_times = [e["executionTimeMs"] for e in availability_events if e.get("condition") == "P3"]
    
    b2_avg = sum(b2_times) / len(b2_times) if b2_times else 0
    p3_avg = sum(p3_times) / len(p3_times) if p3_times else 0
    overhead = p3_avg / b2_avg if b2_avg > 0 else 0
    
    metrics["overhead"] = {
        "value": round(overhead, 4),
        "description": "Execution Overhead (P3/B2)",
        "b2_avg_ms": round(b2_avg, 2),
        "p3_avg_ms": round(p3_avg, 2),
    }
    
    # Build report
    report = {
        "schemaVersion": "finboundbench.statistical-report.v3",
        "status": "PASSED_TEST_DOUBLE_ONLY",
        "instrumentationLabel": INSTRUMENTATION_LABEL,
        "researchClaimsPermitted": False,
        "metrics": metrics,
        "dataSources": {
            "confirmatory": str(confirmatory_path.relative_to(research_root)) if confirmatory_path.exists() else None,
            "attacks": str(attack_path.relative_to(research_root)) if attack_path.exists() else None,
            "dp": str(dp_path.relative_to(research_root)) if dp_path.exists() else None,
            "evidence": str(evidence_path.relative_to(research_root)) if evidence_path.exists() else None,
            "availability": str(availability_path.relative_to(research_root)) if availability_path.exists() else None,
        },
        "limitations": [
            "All metrics computed from test double data.",
            "This analysis validates metric computation plumbing only.",
            "Research claims require live experimental execution."
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
        "schemaVersion": "finboundbench.statistical-analysis-manifest.v3",
        "status": "PASSED_TEST_DOUBLE_ONLY",
        "instrumentationLabel": INSTRUMENTATION_LABEL,
        "metricsComputed": len(metrics),
        "reportHash": report["reportHash"],
    }
    manifest = {**core, "manifestHash": sha256_json(core)}
    
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    
    print(f"Statistical analysis complete:")
    for name, metric in metrics.items():
        print(f"  {name}: {metric['value']} ({metric['description']})")
    
    return manifest


if __name__ == "__main__":
    research_root = Path(__file__).resolve().parents[1]
    manifest = run_statistical_analysis(research_root)
