"""Run protocol-v3 DP experiments using test double oracle."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import sha256_json

INSTRUMENTATION_LABEL = "INSTRUMENTATION_ONLY_NOT_A_RESEARCH_RESULT"
OUTPUT_DIR = Path("results/v3/dp-experiments")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _stable_int(*parts: object) -> int:
    material = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


DP_CONFIGS = {
    "D0": {"epsilon": None, "delta": None, "utility_center": 0.75, "privacy_risk_center": 0.80},
    "D1": {"epsilon": 1.0, "delta": 0.00001, "utility_center": 0.73, "privacy_risk_center": 0.60},
    "D2": {"epsilon": 0.5, "delta": 0.00001, "utility_center": 0.70, "privacy_risk_center": 0.40},
    "D3": {"epsilon": 0.1, "delta": 0.00001, "utility_center": 0.65, "privacy_risk_center": 0.20},
}


def run_dp_experiments(research_root: Path, num_seeds: int = 10) -> dict[str, Any]:
    """Run DP experiments across D0-D3 conditions."""
    target = research_root / OUTPUT_DIR
    raw_path = target / "raw/events.jsonl"
    report_path = target / "derived/dp-report.json"
    manifest_path = target / "manifests/run-manifest.json"
    
    if raw_path.exists() or manifest_path.exists():
        raise FileExistsError(f"DP experiment results already exist: {target}")
    
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    events = []
    condition_results: dict[str, list[dict[str, Any]]] = {}
    
    for condition, config in DP_CONFIGS.items():
        condition_results[condition] = []
        
        for seed in range(num_seeds):
            # Simulate DP training with perturbation
            perturbation = (_stable_int(condition, seed) % 5 - 2) / 1000
            utility = config["utility_center"] + perturbation
            privacy_risk = config["privacy_risk_center"] - perturbation
            
            event = {
                "schemaVersion": "finboundbench.dp-event.v3",
                "instrumentationLabel": INSTRUMENTATION_LABEL,
                "condition": condition,
                "seed": seed,
                "epsilon": config["epsilon"],
                "delta": config["delta"],
                "utility": round(utility, 6),
                "privacyRisk": round(privacy_risk, 6),
                "secureRng": False,
                "measurementType": "TEST_DOUBLE_NOT_DP_TRAINING",
                "timestamp": _now(),
            }
            event["eventHash"] = sha256_json(event)
            events.append(event)
            condition_results[condition].append(event)
    
    # Write raw events
    with raw_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, sort_keys=True) + "\n")
    
    # Compute summary statistics
    summary = {}
    for condition, results in condition_results.items():
        utilities = [r["utility"] for r in results]
        privacy_risks = [r["privacyRisk"] for r in results]
        summary[condition] = {
            "count": len(results),
            "utility_mean": sum(utilities) / len(utilities),
            "utility_min": min(utilities),
            "utility_max": max(utilities),
            "privacy_risk_mean": sum(privacy_risks) / len(privacy_risks),
            "privacy_risk_min": min(privacy_risks),
            "privacy_risk_max": max(privacy_risks),
            "epsilon": DP_CONFIGS[condition]["epsilon"],
            "delta": DP_CONFIGS[condition]["delta"],
        }
    
    # Build report
    report = {
        "schemaVersion": "finboundbench.dp-report.v3",
        "status": "PASSED_TEST_DOUBLE_ONLY",
        "instrumentationLabel": INSTRUMENTATION_LABEL,
        "researchClaimsPermitted": False,
        "totalEvents": len(events),
        "conditionsTested": len(DP_CONFIGS),
        "seedsPerCondition": num_seeds,
        "summary": summary,
        "limitations": [
            "All DP outcomes use deterministic test double.",
            "This run validates DP experiment plumbing only.",
            "No real DP-SGD training was performed.",
            "Privacy claims require live DP-SGD execution."
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
        "schemaVersion": "finboundbench.dp-experiment-manifest.v3",
        "status": "PASSED_TEST_DOUBLE_ONLY",
        "instrumentationLabel": INSTRUMENTATION_LABEL,
        "totalEvents": len(events),
        "conditionsTested": len(DP_CONFIGS),
        "seedsPerCondition": num_seeds,
        "finalEventHash": events[-1]["eventHash"] if events else "0" * 64,
        "completedAt": _now(),
    }
    manifest = {**core, "manifestHash": sha256_json(core)}
    
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
    
    print(f"DP experiments complete:")
    print(f"  Total events: {len(events)}")
    for condition, stats in summary.items():
        print(f"  {condition}: utility={stats['utility_mean']:.4f}, privacy_risk={stats['privacy_risk_mean']:.4f}")
    
    return manifest


if __name__ == "__main__":
    research_root = Path(__file__).resolve().parents[1]
    manifest = run_dp_experiments(research_root)
