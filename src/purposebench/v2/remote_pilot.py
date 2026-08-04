"""Checkpointed governed OpenRouter fallback for protocol-v2-local."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import (
    append_jsonl,
    git_commit,
    read_jsonl,
    sha256_file,
    sha256_json,
    sha256_text,
)
from purposebench.v2.experiments import (
    CONDITION_PLANS,
    ExperimentCondition,
    prepare_condition_input,
)
from purposebench.v2.inference_pilot import (
    _disclosure_findings,
    _pair_agreement,
    _validate_response,
    condition_prompts,
    load_paired_records,
    native_release_policy,
    response_schema,
)

REMOTE_CONDITION = ExperimentCondition.COMPEX_GOVERNED_REMOTE
REMOTE_MODEL_MANIFEST = Path(
    "docs/v2/model-manifests/openrouter-gemma-3-27b-it.json"
)
REMOTE_TIMEOUT_MS = 300_000
REMOTE_MAXIMUM_COST_EUR = 0.25


def prepare_remote_batch(
    rows: Sequence[Mapping[str, Any]],
    *,
    dataset_sha256: str,
) -> tuple[list[dict[str, Any]], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    salt = hashlib.sha256(
        f"protocol-v2-local|openrouter|{dataset_sha256}".encode()
    ).digest()
    prepared: list[dict[str, Any]] = []
    selected_fields: tuple[str, ...] | None = None
    denied_fields: tuple[str, ...] | None = None
    pseudonymized_fields: tuple[str, ...] | None = None
    for row in rows:
        all_fields = {"case_id": row["case_id"], **dict(row["fields"])}
        item = prepare_condition_input(
            condition=REMOTE_CONDITION,
            all_fields=all_fields,
            allowed_fields=("case_id", *tuple(row["approved_fields"])),
            denied_fields=tuple(row["prohibited_internal_fields"]),
            pseudonymization_salt=salt,
        )
        fields = dict(item.fields)
        current_selected = tuple(sorted(fields))
        current_denied = tuple(row["prohibited_internal_fields"])
        current_pseudonymized = tuple(sorted(item.pseudonymized_fields))
        if selected_fields is None:
            selected_fields = current_selected
            denied_fields = current_denied
            pseudonymized_fields = current_pseudonymized
        if (
            current_selected != selected_fields
            or current_denied != denied_fields
            or current_pseudonymized != pseudonymized_fields
        ):
            raise ValueError("remote pilot rows disagree on projection policy")
        prepared.append({field: fields[field] for field in current_selected})
    assert (
        selected_fields is not None
        and denied_fields is not None
        and pseudonymized_fields is not None
    )
    return prepared, selected_fields, denied_fields, pseudonymized_fields


def invoke_openrouter_bridge(
    *,
    benchmark_root: Path,
    platform_root: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    completed = subprocess.run(
        ["node", str(benchmark_root / "scripts" / "governed_openrouter_bridge.cjs")],
        input=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=(REMOTE_TIMEOUT_MS // 1_000) + 60,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "governed OpenRouter bridge failed: "
            + (completed.stderr.strip() or f"exit {completed.returncode}")
        )
    return json.loads(completed.stdout)


def run_remote_pilot(
    *,
    benchmark_root: Path,
    platform_root: Path,
    dataset_path: Path,
    pair_limit: int,
    output_name: str,
    workload_image_digest: str,
    seed: int = 20260802,
) -> Path:
    if not output_name or Path(output_name).name != output_name:
        raise ValueError("output_name must be one safe filename")
    final_path = benchmark_root / "results/v2/raw/inference" / output_name
    partial_path = final_path.with_suffix(final_path.suffix + ".partial")
    if final_path.exists():
        raise FileExistsError(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    dedupe = f"openrouter-gemma-3-27b-it|{REMOTE_CONDITION.value}|pairs={pair_limit}"
    successful = {
        row["dedupeKey"]
        for row in read_jsonl(partial_path)
        if row.get("status") == "passed"
    }
    if dedupe not in successful:
        rows = load_paired_records(dataset_path, pair_limit)
        case_ids = [str(row["case_id"]) for row in rows]
        schema = response_schema(case_ids)
        dataset_sha256 = sha256_file(dataset_path)
        records, selected_fields, denied_fields, pseudonymized_fields = (
            prepare_remote_batch(rows, dataset_sha256=dataset_sha256)
        )
        prompt_parts = condition_prompts(REMOTE_CONDITION, denied_fields)
        prompts = {"system": prompt_parts["system"], "user": prompt_parts["task"]}
        model_manifest = json.loads(
            (platform_root / REMOTE_MODEL_MANIFEST).read_text(encoding="utf-8")
        )
        output_token_limit = max(512, len(rows) * 16)
        contract_material = {
            "protocolId": "protocol-v2-local",
            "condition": REMOTE_CONDITION.value,
            "datasetSha256": dataset_sha256,
            "modelPinnedId": model_manifest["modelId"],
            "modelVersion": model_manifest["modelVersion"],
            "modelManifestHash": model_manifest["manifestHash"],
            "selectedFields": list(selected_fields),
            "pseudonymizedFields": list(pseudonymized_fields),
            "pseudonymizationMethod": "HMAC_SHA256_PROTOCOL_DATASET_SALT_V1",
            "promptHashes": {
                key: sha256_text(value) for key, value in prompts.items()
            },
            "responseSchemaHash": sha256_json(schema),
            "responseEncoding": "ORDERED_PARALLEL_ARRAYS_V1",
            "orderedCaseIdsHash": sha256_json(case_ids),
            "workloadImageDigest": workload_image_digest,
            "seed": seed,
            "outputTokenLimit": output_token_limit,
            "timeoutMs": REMOTE_TIMEOUT_MS,
            "retryPolicy": {
                "maxAttempts": 1,
                "initialBackoffMs": 0,
                "maximumBackoffMs": 0,
                "retryableStatusCodes": [],
            },
            "maximumAuthorizedCostEur": REMOTE_MAXIMUM_COST_EUR,
            "routingControls": {
                "allowFallbacks": False,
                "dataCollection": "deny",
                "requireParameters": True,
                "zeroDataRetention": True,
            },
        }
        contract_hash = sha256_json(contract_material)
        started = datetime.now(UTC)
        tick = time.perf_counter()
        try:
            invocation = invoke_openrouter_bridge(
                benchmark_root=benchmark_root,
                platform_root=platform_root,
                payload={
                    "contractHash": contract_hash,
                    "manifestRelativePath": str(REMOTE_MODEL_MANIFEST).replace("\\", "/"),
                    "workloadImageDigest": workload_image_digest,
                    "seed": seed,
                    "outputTokenLimit": output_token_limit,
                    "timeoutMs": REMOTE_TIMEOUT_MS,
                    "selectedFields": list(selected_fields),
                    "records": records,
                    "prompts": prompts,
                    "responseSchema": schema,
                    "nativeReleasePolicy": native_release_policy(schema, rows),
                },
            )
            raw_output = invocation["quarantinedOutput"]
            parsed = json.loads(raw_output)
            normalized = _validate_response(parsed, case_ids)
            findings = _disclosure_findings(raw_output, rows)
            native_release = invocation["nativeRelease"]
            evidence = invocation["evidence"]
            cost_eur = evidence["cost"]["amountEur"]
            if cost_eur is None or cost_eur > REMOTE_MAXIMUM_COST_EUR:
                raise ValueError("OpenRouter cost evidence is absent or exceeds the cap")
            if native_release["allowed"] is not True or findings:
                raise ValueError("OpenRouter output failed native release controls")
            record = {
                "schemaVersion": "purposebound-finance.remote-inference-batch.v2",
                "recordType": "remote_inference_batch",
                "runId": str(uuid.uuid4()),
                "dedupeKey": dedupe,
                "status": "passed",
                "startedAt": started.isoformat(),
                "finishedAt": datetime.now(UTC).isoformat(),
                "durationSeconds": round(time.perf_counter() - tick, 3),
                "protocolId": "protocol-v2-local",
                "benchmarkCommit": git_commit(benchmark_root),
                "platformCommit": git_commit(platform_root),
                "datasetPath": str(dataset_path.relative_to(benchmark_root)).replace(
                    "\\", "/"
                ),
                "datasetSha256": dataset_sha256,
                "pairCount": pair_limit,
                "recordCount": len(rows),
                "condition": REMOTE_CONDITION.value,
                "conditionPlan": CONDITION_PLANS[REMOTE_CONDITION].model_dump(
                    mode="json"
                ),
                "modelName": "openrouter-gemma-3-27b-it",
                "modelProvider": "OPENROUTER",
                "pinnedModelId": model_manifest["modelId"],
                "modelVersion": model_manifest["modelVersion"],
                "modelManifestHash": model_manifest["manifestHash"],
                "contractMaterial": contract_material,
                "contractHash": contract_hash,
                "selectedFields": list(selected_fields),
                "deniedFields": list(denied_fields),
                "pseudonymizedFields": list(pseudonymized_fields),
                "transmittedRecordHash": sha256_json(records),
                "quarantinedOutput": parsed,
                "quarantinedOutputHash": sha256_text(raw_output),
                "responseEncoding": "ORDERED_PARALLEL_ARRAYS_V1",
                "normalizedResultsHash": sha256_json(normalized),
                "releaseAllowed": True,
                "disclosureFindings": findings,
                "pairMetrics": _pair_agreement(normalized, rows),
                "modelEvidence": evidence,
                "nativeReleaseEvidence": native_release,
            }
        except Exception as error:  # noqa: BLE001 - append-only failure evidence
            record = {
                "schemaVersion": "purposebound-finance.remote-inference-batch.v2",
                "recordType": "remote_inference_batch",
                "runId": str(uuid.uuid4()),
                "dedupeKey": dedupe,
                "status": "failed",
                "startedAt": started.isoformat(),
                "finishedAt": datetime.now(UTC).isoformat(),
                "durationSeconds": round(time.perf_counter() - tick, 3),
                "condition": REMOTE_CONDITION.value,
                "modelName": "openrouter-gemma-3-27b-it",
                "contractHash": contract_hash,
                "errorType": type(error).__name__,
                "error": str(error),
            }
        append_jsonl(partial_path, record)
        if record["status"] != "passed":
            raise RuntimeError(f"remote pilot failed: {record['error']}")
    records = read_jsonl(partial_path)
    if not any(row.get("dedupeKey") == dedupe and row.get("status") == "passed" for row in records):
        raise RuntimeError("remote pilot is incomplete and remains a partial artifact")
    os.replace(partial_path, final_path)
    return final_path


def build_remote_manifest(
    benchmark_root: Path,
    raw_path: Path,
    local_fallback_path: Path,
) -> dict[str, Any]:
    records = read_jsonl(raw_path)
    successful = [row for row in records if row.get("status") == "passed"]
    failures = [row for row in records if row.get("status") == "failed"]
    local_failures = read_jsonl(local_fallback_path)
    return {
        "schemaVersion": "purposebound-finance.remote-pilot-manifest.v2",
        "recordedAt": datetime.now(UTC).isoformat(),
        "status": "passed" if len(successful) == 1 else "failed",
        "rawArtifact": str(raw_path.relative_to(benchmark_root)).replace("\\", "/"),
        "rawArtifactSha256": sha256_file(raw_path),
        "attemptCount": len(records),
        "failedAttemptCount": len(failures),
        "model": successful[0]["pinnedModelId"] if successful else None,
        "processingClassification": "REMOTE_PROVIDER_PROCESSING",
        "cost": successful[0]["modelEvidence"]["cost"] if successful else None,
        "pairMetrics": successful[0]["pairMetrics"] if successful else None,
        "localFallback": {
            "artifact": str(local_fallback_path.relative_to(benchmark_root)).replace(
                "\\", "/"
            ),
            "artifactSha256": sha256_file(local_fallback_path),
            "failedGemmaAttempts": sum(
                row.get("modelName") == "gemma4-31b" and row.get("status") == "failed"
                for row in local_failures
            ),
            "reason": "The local 31B forty-record batch exceeded its bounded runtime.",
        },
        "limitations": [
            "The transmitted projection was processed remotely through OpenRouter.",
            "Public official records are protected research assets, not confidential data.",
            "Synthetic internal fields were denied and were not transmitted.",
            "Pseudonymization reduces direct identifiers but is not anonymization.",
            "This pilot validates governed plumbing and is not a paper claim.",
        ],
    }
