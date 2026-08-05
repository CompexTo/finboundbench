"""Reduced-scope confirmatory run (50 pairs) for validation before full 200-pair run."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from purposebench.utils import (
    append_jsonl,
    canonical_json,
    read_jsonl,
    sha256_json,
)
from purposebench.v3.budget import (
    reserve_budget,
    settle_budget,
    committed_budget_eur,
)
from purposebench.v3.openrouter_metadata import (
    CATALOG_URL,
    ZDR_ENDPOINTS_URL,
    build_model_manifest,
    parse_metadata_response,
    response_sha256,
    select_route,
)

CONFIG_PATH = Path("configs/v3/openrouter-confirmatory-matrix-v3.yaml")
BRIDGE_PATH = Path("scripts/governed_openrouter_bridge_v3.cjs")
OUTPUT_DIR = Path("results/v3/confirmatory-reduced")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _load_config(root: Path) -> dict[str, Any]:
    value = yaml.safe_load((root / CONFIG_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("OpenRouter confirmatory config must be a mapping")
    return value


def _load_pairs(root: Path, dataset_id: str, pair_limit: int) -> list[dict[str, Any]]:
    if dataset_id == "hmda-2024-dc-v3":
        path = root / "data/v2/generated/hmda-2024-dc-pairs.jsonl"
    elif dataset_id == "cfpb-complaints-2024-01-dc-v3":
        path = root / "data/v2/generated/cfpb-2024-01-dc-pairs.jsonl"
    else:
        raise ValueError(f"unknown dataset: {dataset_id}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[:pair_limit]


def _build_conditions() -> list[dict[str, Any]]:
    return [
        {"id": "B0", "name": "full_data_no_purpose_policy", "purpose_binding": False},
        {"id": "P3", "name": "psbe_full_evidence", "purpose_binding": True},
    ]


def _build_payload(
    config: dict[str, Any],
    model_id: str,
    route: str,
    manifest_hash: str,
    condition: dict[str, Any],
    pair: dict[str, Any],
    repetition: int,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    material = {
        "admissionId": config["admission_id"],
        "model": model_id,
        "route": route,
        "selectedFields": config["selected_fields"],
        "recordsHash": sha256_json(records),
        "promptsHash": sha256_json(config["prompts"]),
        "responseSchemaHash": sha256_json(config["response_schema"]),
        "conditionId": condition["id"],
        "pairId": str(pair.get("pair_id", "")),
        "repetition": repetition,
        "seed": config["seed"],
    }
    return {
        "contractHash": sha256_json(material),
        "manifestRelativePath": f"docs/v3/model-manifests/openrouter-{model_id.replace('/', '-')}.json",
        "workloadImageDigest": config["workload_image_digest"],
        "seed": config["seed"],
        "outputTokenLimit": config["output_token_limit"],
        "timeoutMs": config["timeout_ms"],
        "selectedFields": config["selected_fields"],
        "records": records,
        "prompts": config["prompts"],
        "responseSchema": config["response_schema"],
        "nativeReleasePolicy": {
            "policyRuleId": "finboundbench-v3-r2-confirmatory",
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


def _append_chained(path: Path, core: dict[str, Any], previous: str) -> str:
    event = {**core, "previousEventHash": previous}
    event_hash = sha256_json(event)
    append_jsonl(path, {**event, "eventHash": event_hash})
    return event_hash


def run_reduced_confirmatory(
    research_root: Path,
    platform_root: Path,
    *,
    pairs_per_dataset: int = 50,
    max_calls: int = 500,
) -> dict[str, Any]:
    """Run reduced-scope confirmatory matrix with pairs_per_dataset pairs."""
    config = _load_config(research_root)
    target = research_root / OUTPUT_DIR
    raw_path = target / "raw/events.jsonl"
    manifest_path = target / "manifests/run-manifest.json"
    
    if raw_path.exists() or manifest_path.exists():
        raise FileExistsError(f"Reduced confirmatory results already exist: {target}")
    
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    ledger_path = target / "raw/budget/reduced-ledger.jsonl"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    
    conditions = _build_conditions()
    datasets = ["hmda-2024-dc-v3", "cfpb-complaints-2024-01-dc-v3"]
    actual_pairs_per_dataset = min(pairs_per_dataset, 40)  # Max available in datasets
    pairs_by_dataset = {ds: _load_pairs(research_root, ds, actual_pairs_per_dataset) for ds in datasets}
    
    actual_pairs_per_dataset = min(pairs_per_dataset, 40)  # Max available in datasets
    print(f"Reduced scope: {actual_pairs_per_dataset} pairs per dataset (max available: 40)")
    print(f"Total expected invocations: {len(datasets)} datasets × {len(conditions)} conditions × {len(config['models'])} models × {actual_pairs_per_dataset} pairs × 3 reps = {len(datasets) * len(conditions) * len(config['models']) * actual_pairs_per_dataset * 3}")
    
    previous = "0" * 64
    attempts = 0
    passed = 0
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    environment["FINBOUNDBENCH_ROOT"] = str(research_root)
    
    # Fetch catalog and routes once
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        catalog_response = client.get(CATALOG_URL, headers={"accept": "application/json"})
        route_response = client.get(ZDR_ENDPOINTS_URL, headers={"accept": "application/json"})
    catalog_response.raise_for_status()
    route_response.raise_for_status()
    catalog_rows = parse_metadata_response(catalog_response.content, source="catalog")
    route_rows = parse_metadata_response(route_response.content, source="endpoints")
    catalog_hash = response_sha256(catalog_response.content)
    route_hash = response_sha256(route_response.content)
    
    for model in config["models"]:
        if attempts >= max_calls:
            break
            
        model_id = model["expected_model_id"]
        preferred_route = model["expected_upstream_route"]
        lane_id = model["lane_id"]
        
        print(f"\nProcessing model: {model_id} (lane: {lane_id})")
        
        # Capture fresh manifest
        try:
            _, route, _ = select_route(model_id, catalog_rows, route_rows, preferred_tag=preferred_route)
            manifest = build_model_manifest(
                model={"id": model_id, **{k: v for k, v in catalog_rows[0].items() if k == "id"}},
                route=route,
                captured_at=_now(),
                catalog_artifact="live-capture",
                catalog_response_hash=catalog_hash,
                route_artifact="live-capture",
                route_response_hash=route_hash,
            )
            manifest_hash = manifest["manifestHash"]
            upstream_route = route["tag"]
            print(f"  Manifest captured: {manifest_hash[:16]}...")
        except Exception as e:
            print(f"  Failed to capture manifest: {e}")
            continue
        
        for condition in conditions:
            if attempts >= max_calls:
                break
                
            for dataset_id, pairs in pairs_by_dataset.items():
                if attempts >= max_calls:
                    break
                    
                print(f"  Condition: {condition['id']}, Dataset: {dataset_id}, Pairs: {len(pairs)}")
                
                for pair in pairs:
                    if attempts >= max_calls:
                        break
                        
                    for repetition in range(1, 4):
                        if attempts >= max_calls:
                            break
                            
                        attempts += 1
                        fields = pair.get("fields", {})
                        approved = pair.get("approved_fields", [])
                        selected = config["selected_fields"]
                        record = {}
                        for field in selected:
                            if field in fields and field in approved:
                                record[field] = fields[field]
                        records = [record] if record else []
                        
                        payload = _build_payload(
                            config, model_id, upstream_route, manifest_hash,
                            condition, pair, repetition, records,
                        )
                        started_at = _now()
                        reservation_id = reserve_budget(
                            ledger_path,
                            model_id=model_id,
                            phase=f"R2_{condition['id']}_{dataset_id}",
                            authorization_id=config["budget"]["authorization_id"],
                            authorized_cost_eur=float(config["budget"]["reservation_per_call_eur"]),
                            phase_authorized_eur=float(config["budget"]["phase_authorized_eur"]),
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
                                model_id=model_id,
                                phase=f"R2_{condition['id']}_{dataset_id}",
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
                                model_id=model_id,
                                phase=f"R2_{condition['id']}_{dataset_id}",
                                authorization_id=config["budget"]["authorization_id"],
                                budget_debit_eur=float(config["budget"]["reservation_per_call_eur"]),
                                outcome="failed_conservative_debit",
                                provider_reported_cost=None,
                            )
                        
                        previous = _append_chained(
                            raw_path,
                            {
                                "schemaVersion": "finboundbench.confirmatory-matrix-event.v3",
                                "matrixLabel": "V3_CONFIRMATORY_MATRIX_REDUCED",
                                "sequence": attempts,
                                "laneId": lane_id,
                                "expectedModelId": model_id,
                                "conditionId": condition["id"],
                                "datasetId": dataset_id,
                                "pairId": str(pair.get("pair_id", "")),
                                "repetition": repetition,
                                "contractHash": payload["contractHash"],
                                "reservationId": reservation_id,
                                "startedAt": started_at,
                                "completedAt": _now(),
                                **outcome,
                            },
                            previous,
                        )
                        
                        # Progress indicator
                        if attempts % 10 == 0:
                            print(f"    Progress: {attempts} attempts, {passed} passed")
                        
                        # Delay to avoid rate limiting (increased from 0.5s)
                        time.sleep(2.0)
    
    # Build manifest
    ledger_rows = read_jsonl(ledger_path)
    core = {
        "schemaVersion": "finboundbench.confirmatory-matrix-run.v3",
        "matrixLabel": "V3_CONFIRMATORY_MATRIX_REDUCED",
        "admissionId": config["admission_id"],
        "status": "PASSED" if passed == attempts else "COMPLETED_WITH_FAILURES",
        "pairsPerDataset": actual_pairs_per_dataset,
        "modelsTested": len(config["models"]),
        "conditionsTested": len(conditions),
        "datasetsTested": len(datasets),
        "repetitions": 3,
        "attempts": attempts,
        "passed": passed,
        "failedOrDenied": attempts - passed,
        "finalEventHash": previous,
        "budget": {
            "ledgerPath": str(ledger_path.relative_to(research_root)),
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
    
    print(f"\nReduced confirmatory run complete:")
    print(f"  Attempts: {attempts}")
    print(f"  Passed: {passed}")
    print(f"  Cost: €{manifest['budget']['committedEur']:.2f}")
    print(f"  Manifest: {manifest_path}")
    
    return manifest


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs-per-dataset", type=int, default=40)
    parser.add_argument("--max-calls", type=int, default=500)
    args = parser.parse_args()
    
    research_root = Path(__file__).resolve().parents[1]
    platform_root = research_root.parents[1]
    
    manifest = run_reduced_confirmatory(
        research_root,
        platform_root,
        pairs_per_dataset=args.pairs_per_dataset,
        max_calls=args.max_calls,
    )
