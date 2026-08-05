"""v3 position and batch diagnostic for admitted OpenRouter models.

Tests that admitted models can handle different batch layouts and positions.
This is R1 in the protocol - a diagnostic phase that validates model behavior
before the confirmatory R2 matrix.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from purposebench.utils import (
    append_jsonl,
    canonical_json,
    read_jsonl,
    sha256_json,
)
from purposebench.v3.budget import (
    LEDGER_PATH,
    committed_budget_eur,
    reserve_budget,
    settle_budget,
)

POSITION_LABEL = "V3_POSITION_BATCH_DIAGNOSTIC"
CONFIG_PATH = Path("configs/v3/openrouter-model-admission-v3.yaml")
BRIDGE_PATH = Path("scripts/governed_openrouter_bridge_v3.cjs")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _load_config(root: Path) -> dict[str, Any]:
    value = yaml.safe_load((root / CONFIG_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("OpenRouter admission config must be a mapping")
    return value


def _load_pilot_data(root: Path) -> list[dict[str, Any]]:
    path = root / "data/generated/pilot_40.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) < 8:
        raise ValueError("pilot data has too few rows for position diagnostic")
    return rows


def _build_layouts(rows: list[dict[str, Any]], seed: int = 20260805) -> list[dict[str, Any]]:
    """Build different batch layouts for position diagnostic."""
    base = rows[:8]
    shuffled = list(base)
    random.Random(seed).shuffle(shuffled)
    
    layouts = [
        {"layout": "original_order", "batch": base},
        {"layout": "reversed_order", "batch": list(reversed(base))},
        {"layout": "deterministic_shuffle", "batch": shuffled},
        {"layout": "singleton_first", "batch": [base[0]]},
        {"layout": "small_batch_first_4", "batch": base[:4]},
        {"layout": "small_batch_last_4", "batch": base[4:]},
    ]
    return layouts


def _build_position_payload(
    config: dict[str, Any],
    model: dict[str, Any],
    batch: list[dict[str, Any]],
    layout: str,
) -> dict[str, Any]:
    """Build bridge payload for a position diagnostic invocation."""
    records = []
    for row in batch:
        record = {}
        for field in config["selected_fields"]:
            if field in row.get("all_fields", {}):
                record[field] = row["all_fields"][field]
            elif field in row.get("allowed_fields", {}):
                record[field] = row["allowed_fields"][field]
        if record:
            records.append(record)
    
    material = {
        "admissionId": config["admission_id"],
        "model": model["expected_model_id"],
        "route": model["expected_upstream_route"],
        "selectedFields": config["selected_fields"],
        "recordsHash": sha256_json(records),
        "promptsHash": sha256_json(config["prompts"]),
        "responseSchemaHash": sha256_json(config["response_schema"]),
        "layout": layout,
        "seed": config["seed"],
    }
    
    return {
        "contractHash": sha256_json(material),
        "manifestRelativePath": model["manifest_path"],
        "workloadImageDigest": config["workload_image_digest"],
        "seed": config["seed"],
        "outputTokenLimit": config["output_token_limit"],
        "timeoutMs": config["timeout_ms"],
        "selectedFields": config["selected_fields"],
        "records": records,
        "prompts": config["prompts"],
        "responseSchema": config["response_schema"],
        "nativeReleasePolicy": {
            "policyRuleId": "finboundbench-v3-r1-position-diagnostic",
            "requiredValidators": [
                "compex.output.json-schema",
                "compex.output.required-fields",
                "compex.output.decision-vocabulary",
            ],
            "jsonSchema": {"schema": config["response_schema"]},
            "requiredFields": {"paths": ["/decision", "/score", "/reason"]},
            "decisionVocabulary": {
                "path": "/decision",
                "permittedValues": ["STANDARD_QUEUE", "PRIORITY_QUEUE"],
            },
            "numericBounds": {
                "bounds": [{"path": "/score", "minimum": 0, "maximum": 100, "integer": True}]
            },
            "maxBytes": {"maximumBytes": 8192},
            "prohibitedExactValues": {"values": config["prohibited_exact_values"]},
            "prohibitedFieldNames": {"names": config["denied_fields"], "caseInsensitive": True},
            "artifactType": {"permittedTypes": ["application/json"]},
            "modelRelease": {"permitted": False},
        },
        "maximumAuthorizedCostEur": float(config["budget"]["reservation_per_call_eur"]),
    }


def run_position_diagnostic(
    research_root: Path,
    platform_root: Path,
    *,
    layouts: list[str] | None = None,
) -> dict[str, Any]:
    """Run position diagnostic for all admitted models."""
    config = _load_config(research_root)
    raw_path = research_root / "results/v3/position-diagnostic/raw/events.jsonl"
    manifest_path = research_root / "results/v3/position-diagnostic/manifests/run-manifest.json"
    
    if raw_path.exists() or manifest_path.exists():
        raise FileExistsError("Position diagnostic results already exist")
    
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    ledger_path = research_root / LEDGER_PATH
    rows = _load_pilot_data(research_root)
    all_layouts = _build_layouts(rows)
    
    if layouts:
        all_layouts = [l for l in all_layouts if l["layout"] in layouts]
    
    previous = "0" * 64
    attempts = 0
    passed = 0
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    environment["FINBOUNDBENCH_ROOT"] = str(research_root)
    
    protocol_path = research_root / "configs/v3/protocol-v3-psbe-no-tee.yaml"
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    admitted_lane_ids = {
        c["lane_id"] for c in protocol.get("models", {}).get("candidates", [])
        if c.get("r0_admission") == "ADMITTED"
    }
    admitted_models = [m for m in config["models"] if m["lane_id"] in admitted_lane_ids]
    for model in admitted_models:
        for layout_info in all_layouts:
            attempts += 1
            payload = _build_position_payload(
                config, model, layout_info["batch"], layout_info["layout"]
            )
            started_at = _now()
            reservation_id = reserve_budget(
                ledger_path,
                model_id=model["expected_model_id"],
                phase=f"R1_position_{layout_info['layout']}",
                authorization_id=config["budget"]["authorization_id"],
                authorized_cost_eur=float(config["budget"]["reservation_per_call_eur"]),
                phase_authorized_eur=float(config["budget"]["absolute_authorized_eur"]),
                absolute_authorized_eur=float(config["budget"]["absolute_authorized_eur"]),
            )
            
            try:
                completed = subprocess.run(
                    ["node", str(research_root / BRIDGE_PATH)],
                    input=canonical_json(payload),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=environment,
                    timeout=(config["timeout_ms"] // 1000) + 120,
                    check=False,
                )
                if completed.returncode != 0:
                    raise RuntimeError(completed.stderr.strip() or f"bridge exit {completed.returncode}")
                result = json.loads(completed.stdout)
                released = bool(result.get("nativeRelease", {}).get("allowed"))
                evidence = result.get("evidence", {})
                provider_reported_cost = evidence.get("providerReportedCost")
                calculated = evidence.get("cost", {})
                debit = float(
                    calculated.get("amountEur")
                    if calculated.get("amountEur") is not None
                    else config["budget"]["reservation_per_call_eur"]
                )
                
                if released:
                    passed += 1
                outcome = {
                    "status": "PASSED" if released else "RELEASE_DENIED",
                    "result": result,
                    "errorClass": None,
                    "errorMessage": None,
                }
                settle_budget(
                    ledger_path,
                    reservation_id=reservation_id,
                    model_id=model["expected_model_id"],
                    phase=f"R1_position_{layout_info['layout']}",
                    authorization_id=config["budget"]["authorization_id"],
                    budget_debit_eur=min(debit, float(config["budget"]["reservation_per_call_eur"])),
                    outcome="passed" if released else "release_denied",
                    provider_reported_cost=provider_reported_cost,
                )
            except Exception as error:
                outcome = {
                    "status": "FAILED",
                    "result": None,
                    "errorClass": type(error).__name__,
                    "errorMessage": str(error)[:2000],
                }
                settle_budget(
                    ledger_path,
                    reservation_id=reservation_id,
                    model_id=model["expected_model_id"],
                    phase=f"R1_position_{layout_info['layout']}",
                    authorization_id=config["budget"]["authorization_id"],
                    budget_debit_eur=float(config["budget"]["reservation_per_call_eur"]),
                    outcome="failed_conservative_debit",
                    provider_reported_cost=None,
                )
            
            previous = _append_chained(
                raw_path,
                {
                    "schemaVersion": "finboundbench.position-diagnostic-event.v3",
                    "diagnosticLabel": POSITION_LABEL,
                    "sequence": attempts,
                    "laneId": model["lane_id"],
                    "expectedModelId": model["expected_model_id"],
                    "layout": layout_info["layout"],
                    "batchSize": len(layout_info["batch"]),
                    "contractHash": payload["contractHash"],
                    "reservationId": reservation_id,
                    "startedAt": started_at,
                    "completedAt": _now(),
                    **outcome,
                },
                previous,
            )
    
    ledger_rows = read_jsonl(ledger_path)
    core = {
        "schemaVersion": "finboundbench.position-diagnostic-run.v3",
        "diagnosticLabel": POSITION_LABEL,
        "admissionId": config["admission_id"],
        "status": "PASSED" if passed == attempts else "COMPLETED_WITH_FAILURES",
        "modelsTested": len(config["models"]),
        "layoutsTested": len(all_layouts),
        "attempts": attempts,
        "passed": passed,
        "failedOrDenied": attempts - passed,
        "finalEventHash": previous,
        "budget": {
            "ledgerPath": LEDGER_PATH.as_posix(),
            "ledgerRecordCount": len(ledger_rows),
            "ledgerHash": sha256_json(ledger_rows),
            "committedEur": committed_budget_eur(ledger_rows),
        },
        "completedAt": _now(),
    }
    manifest = {**core, "manifestHash": sha256_json(core)}
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _append_chained(path: Path, core: dict[str, Any], previous: str) -> str:
    event = {**core, "previousEventHash": previous}
    event_hash = sha256_json(event)
    append_jsonl(path, {**event, "eventHash": event_hash})
    return event_hash


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument("--layouts", nargs="*", help="Specific layouts to test")
    args = parser.parse_args()
    research_root = Path(__file__).resolve().parents[1]
    manifest = run_position_diagnostic(
        research_root,
        args.platform_root.resolve(),
        layouts=args.layouts,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "attempts": manifest["attempts"],
                "passed": manifest["passed"],
                "committedEur": manifest["budget"]["committedEur"],
            },
            sort_keys=True,
        )
    )
    if manifest["status"] != "PASSED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
