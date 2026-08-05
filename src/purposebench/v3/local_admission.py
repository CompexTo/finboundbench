"""Frozen, no-cost admission gate for exact local Ollama models."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from purposebench.utils import (
    append_jsonl,
    canonical_json,
    git_commit,
    git_provenance,
    read_jsonl,
    sha256_file,
    sha256_json,
)

ADMISSION_LABEL = "LOCAL_MODEL_ADMISSION_DIAGNOSTIC_NOT_CONFIRMATORY"
CONFIG_PATH = Path("configs/v3/local-model-admission-v3.yaml")
BRIDGE_PATH = Path("scripts/governed_ollama_bridge_v3.cjs")
RESEARCH_ARTIFACTS = (
    CONFIG_PATH,
    BRIDGE_PATH,
    Path("scripts/capture_v3_ollama_manifests.py"),
    Path("src/purposebench/v3/local_admission.py"),
    Path("scripts/build_v3_local_model_admission_freeze.py"),
    Path("scripts/run_v3_local_model_admission.py"),
    Path("scripts/verify_v3_local_model_admission.py"),
    Path("docs/v3/model-manifests/gemma4-e2b.json"),
    Path("docs/v3/model-manifests/qwen3-4b.json"),
    Path("docs/v3/model-manifests/gemma4-31b.json"),
)
PLATFORM_ARTIFACTS = (
    Path("packages/types/src/confidential-execution.ts"),
    Path("services/runner/src/local-models/ollama-model.adapter.ts"),
    Path("services/api/src/confidential-execution/release/native-output-release.ts"),
)
FORBIDDEN_SECRET_MARKERS = (
    "OPENROUTER_API_KEY",
    "sk-or-v1-",
    "authorization: bearer",
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _read_config(root: Path) -> dict[str, Any]:
    value = yaml.safe_load((root / CONFIG_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("local admission config must be a mapping")
    return value


def _safe_path(root: Path, relative: str, expected_parent: Path) -> Path:
    candidate = (root / relative).resolve()
    allowed = (root / expected_parent).resolve()
    if candidate != allowed and allowed not in candidate.parents:
        raise ValueError(f"path escaped {expected_parent}: {relative}")
    return candidate


def _validate_manifest(value: dict[str, Any], model: dict[str, Any]) -> None:
    if value.get("schema") != "compex-ollama-model-manifest-v2":
        raise ValueError("unexpected Ollama manifest schema")
    manifest_hash = value.get("manifestHash")
    core = {key: item for key, item in value.items() if key != "manifestHash"}
    if not isinstance(manifest_hash, str) or sha256_json(core) != manifest_hash:
        raise ValueError("Ollama manifest hash mismatch")
    if manifest_hash != model.get("expected_manifest_hash"):
        raise ValueError("configured Ollama manifest hash mismatch")
    if value.get("modelTag") != model.get("expected_model_tag"):
        raise ValueError("configured Ollama model tag mismatch")
    if value.get("pinnedModelId") != model.get("expected_pinned_model_id"):
        raise ValueError("configured pinned Ollama identity mismatch")
    if value.get("pinnedModelId") != (
        f"{value.get('modelTag')}@{value.get('manifestDigest')}"
    ):
        raise ValueError("Ollama identity is not bound to its manifest digest")
    if re.search(r"(^|[:_.-])(latest|current|default|stable|preview)([:_.-]|$)", str(value.get("modelTag")), re.I):
        raise ValueError("mutable Ollama alias is prohibited")


def validate_local_admission_config(root: Path, config: dict[str, Any]) -> None:
    """Fail closed before a local model process can be invoked."""

    exact = {
        "schema_version": "finboundbench.local-model-admission.v3",
        "scope": "LOCAL_SCHEMA_AND_GOVERNANCE_DIAGNOSTIC_NOT_CONFIRMATORY",
        "remote_provider_calls_permitted": 0,
        "paid_secrets_permitted": False,
        "aws_actions_permitted": False,
        "confirmatory_claims_permitted": False,
        "hardware_attestation": False,
        "host_trust_required": True,
        "automatic_retries": 0,
        "fallback_permitted": False,
        "keep_alive_seconds": 0,
    }
    for key, expected in exact.items():
        if config.get(key) != expected:
            raise ValueError(f"unsafe or invalid local admission setting: {key}")
    for key, low, high in (
        ("context_window_tokens", 4096, 65536),
        ("output_token_limit", 1, 1024),
        ("timeout_ms", 1, 86_400_000),
    ):
        value = config.get(key)
        if not isinstance(value, int) or not low <= value <= high:
            raise ValueError(f"invalid local admission bound: {key}")
    expected_bridge_digest = f"sha256:{sha256_file(root / BRIDGE_PATH)}"
    if config.get("workload_image_digest") != expected_bridge_digest:
        raise ValueError("bridge source changed without updating workload digest")
    if config.get("workload_digest_semantics") != (
        "SHA256_OF_HOST_BRIDGE_SOURCE_NOT_A_CONTAINER_OR_ATTESTATION"
    ):
        raise ValueError("workload digest semantics became ambiguous")
    selected = config.get("selected_fields")
    denied = config.get("denied_fields")
    records = config.get("records")
    if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected):
        raise ValueError("selected fields must be a unique nonempty list")
    if not isinstance(denied, list) or set(selected) & set(denied):
        raise ValueError("selected and denied fields overlap")
    if not isinstance(records, list) or len(records) != 1 or set(records[0]) != set(selected):
        raise ValueError("admission record is not an exact approved projection")
    projected = canonical_json(records)
    if any(str(value) in projected for value in config.get("prohibited_exact_values", [])):
        raise ValueError("prohibited exact value entered the admission projection")
    if any(str(field) in projected for field in denied):
        raise ValueError("denied field entered the admission projection")
    if not isinstance(config.get("prompts"), dict) or not isinstance(
        config.get("response_schema"), dict
    ):
        raise TypeError("prompts and response schema must be mappings")
    models = config.get("models")
    if not isinstance(models, list) or len(models) != 3:
        raise ValueError("exactly three preregistered local model lanes are required")
    lane_ids = [model.get("lane_id") for model in models]
    if len(set(lane_ids)) != 3:
        raise ValueError("local model lane IDs must be unique")
    for model in models:
        manifest_path = _safe_path(
            root, str(model.get("manifest_path", "")), Path("docs/v3/model-manifests")
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_manifest(manifest, model)


def native_release_policy(config: dict[str, Any]) -> dict[str, Any]:
    required = [
        "compex.output.json-schema",
        "compex.output.required-fields",
        "compex.output.decision-vocabulary",
        "compex.output.numeric-bounds",
        "compex.output.max-bytes",
        "compex.output.prohibited-exact-values",
        "compex.output.prohibited-field-names",
        "compex.output.pii-patterns",
        "compex.output.artifact-type",
        "compex.output.model-release",
    ]
    return {
        "policyRuleId": "finboundbench-v3-local-admission-release",
        "requiredValidators": required,
        "jsonSchema": {"schema": config["response_schema"]},
        "requiredFields": {"paths": ["/decision", "/score", "/reason"]},
        "decisionVocabulary": {
            "path": "/decision",
            "permittedValues": ["STANDARD_QUEUE", "PRIORITY_QUEUE"],
        },
        "numericBounds": {
            "bounds": [{"path": "/score", "minimum": 0, "maximum": 100, "integer": True}]
        },
        "maxBytes": {"maximumBytes": 4096},
        "prohibitedExactValues": {"values": config["prohibited_exact_values"]},
        "prohibitedFieldNames": {"names": config["denied_fields"], "caseInsensitive": True},
        "piiPatterns": {"patterns": ["EMAIL", "US_SSN", "IBAN", "CREDIT_CARD"]},
        "artifactType": {"permittedTypes": ["application/json"]},
        "modelRelease": {"permitted": False},
    }


def build_bridge_payload(config: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    material = {
        "admissionId": config["admission_id"],
        "model": model["expected_pinned_model_id"],
        "selectedFields": config["selected_fields"],
        "recordsHash": sha256_json(config["records"]),
        "promptsHash": sha256_json(config["prompts"]),
        "responseSchemaHash": sha256_json(config["response_schema"]),
        "releasePolicyHash": sha256_json(native_release_policy(config)),
        "seed": config["seed"],
    }
    return {
        "contractHash": sha256_json(material),
        "manifestRelativePath": model["manifest_path"],
        "workloadImageDigest": config["workload_image_digest"],
        "seed": config["seed"],
        "outputTokenLimit": config["output_token_limit"],
        "contextWindowTokens": config["context_window_tokens"],
        "timeoutMs": config["timeout_ms"],
        "keepAliveSeconds": config["keep_alive_seconds"],
        "selectedFields": config["selected_fields"],
        "records": config["records"],
        "prompts": config["prompts"],
        "responseSchema": config["response_schema"],
        "nativeReleasePolicy": native_release_policy(config),
    }


def _artifact(root: Path, path: Path, repository: str) -> dict[str, Any]:
    absolute = root / path
    return {
        "repository": repository,
        "path": path.as_posix(),
        "sha256": sha256_file(absolute),
        "bytes": absolute.stat().st_size,
    }


def build_local_admission_freeze(
    research_root: Path,
    platform_root: Path,
    *,
    research_commit: str,
    platform_commit: str,
) -> dict[str, Any]:
    config = _read_config(research_root)
    validate_local_admission_config(research_root, config)
    artifacts = [
        *(_artifact(research_root, path, "research") for path in RESEARCH_ARTIFACTS),
        *(_artifact(platform_root, path, "platform") for path in PLATFORM_ARTIFACTS),
    ]
    core = {
        "schemaVersion": "finboundbench.local-model-admission-freeze.v3",
        "admissionId": config["admission_id"],
        "scope": config["scope"],
        "status": "FROZEN_LOCAL_DIAGNOSTIC_ONLY",
        "frozenAt": _now(),
        "repositoryBindings": {
            "researchCommit": research_commit,
            "platformCommit": platform_commit,
        },
        "repositoryStateAtFreeze": {
            "research": git_provenance(research_root),
            "platform": git_provenance(platform_root),
            "platformScopeBoundByArtifactHashes": True,
            "unrelatedUserChangesIncluded": False,
        },
        "remoteProviderCallsPermitted": 0,
        "providerSecretPermitted": False,
        "awsActionsPermitted": False,
        "confirmatoryClaimsPermitted": False,
        "hardwareAttestation": False,
        "modelManifestHashes": [
            model["expected_manifest_hash"] for model in config["models"]
        ],
        "artifacts": artifacts,
    }
    return {**core, "freezeManifestHash": sha256_json(core)}


def _is_ancestor(root: Path, ancestor: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
    ).returncode == 0


def verify_local_admission_freeze(
    research_root: Path, platform_root: Path
) -> dict[str, Any]:
    config = _read_config(research_root)
    validate_local_admission_config(research_root, config)
    path = research_root / config["freeze_manifest_path"]
    value = json.loads(path.read_text(encoding="utf-8"))
    claimed_hash = value.pop("freezeManifestHash", None)
    if not isinstance(claimed_hash, str) or sha256_json(value) != claimed_hash:
        raise ValueError("local admission freeze self-hash mismatch")
    value["freezeManifestHash"] = claimed_hash
    bindings = value["repositoryBindings"]
    if not _is_ancestor(research_root, bindings["researchCommit"]):
        raise ValueError("frozen research commit is not an ancestor of HEAD")
    if not _is_ancestor(platform_root, bindings["platformCommit"]):
        raise ValueError("frozen platform commit is not an ancestor of HEAD")
    roots = {"research": research_root, "platform": platform_root}
    for artifact in value["artifacts"]:
        artifact_path = roots[artifact["repository"]] / artifact["path"]
        if artifact_path.stat().st_size != artifact["bytes"] or sha256_file(
            artifact_path
        ) != artifact["sha256"]:
            raise ValueError(f"frozen artifact changed: {artifact['path']}")
    return value


def _append_chained(path: Path, core: dict[str, Any], previous: str) -> str:
    event = {**core, "previousEventHash": previous}
    event_hash = sha256_json(event)
    append_jsonl(path, {**event, "eventHash": event_hash})
    return event_hash


def run_local_model_admission(
    research_root: Path, platform_root: Path
) -> dict[str, Any]:
    freeze = verify_local_admission_freeze(research_root, platform_root)
    config = _read_config(research_root)
    raw_path = research_root / config["raw_events_path"]
    manifest_path = research_root / config["run_manifest_path"]
    if raw_path.exists() or manifest_path.exists():
        raise FileExistsError("local admission results already exist; append-only run will not overwrite")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    previous = "0" * 64
    attempts = 0
    allowed = 0
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    environment["FINBOUNDBENCH_ROOT"] = str(research_root)
    for sequence, model in enumerate(config["models"], start=1):
        attempts += 1
        payload = build_bridge_payload(config, model)
        started_at = _now()
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
            if released:
                allowed += 1
            outcome = {
                "status": "ADMITTED" if released else "RELEASE_DENIED",
                "result": result,
                "errorClass": None,
                "errorMessage": None,
            }
        except Exception as error:  # every failure must become append-only evidence
            outcome = {
                "status": "FAILED",
                "result": None,
                "errorClass": type(error).__name__,
                "errorMessage": str(error)[:2000],
            }
        previous = _append_chained(
            raw_path,
            {
                "schemaVersion": "finboundbench.local-model-admission-event.v3",
                "admissionLabel": ADMISSION_LABEL,
                "sequence": sequence,
                "laneId": model["lane_id"],
                "expectedPinnedModelId": model["expected_pinned_model_id"],
                "expectedManifestHash": model["expected_manifest_hash"],
                "contractHash": payload["contractHash"],
                "projectionHash": sha256_json(config["records"]),
                "selectedFields": config["selected_fields"],
                "remoteProviderCalls": 0,
                "providerCostEur": 0,
                "paidSecretRead": False,
                "awsActions": 0,
                "hardwareAttestation": False,
                "hostTrustRequired": True,
                "automaticRetries": 0,
                "fallbackUsed": False,
                "startedAt": started_at,
                "completedAt": _now(),
                **outcome,
            },
            previous,
        )
    raw_artifact = {
        "path": config["raw_events_path"],
        "sha256": sha256_file(raw_path),
        "bytes": raw_path.stat().st_size,
        "events": attempts,
    }
    core = {
        "schemaVersion": "finboundbench.local-model-admission-run.v3",
        "admissionLabel": ADMISSION_LABEL,
        "admissionId": config["admission_id"],
        "status": "PASSED_LOCAL_ADMISSION" if allowed == attempts else "COMPLETED_WITH_RETAINED_FAILURES",
        "freezeManifestHash": freeze["freezeManifestHash"],
        "repositoryBindings": freeze["repositoryBindings"],
        "attempts": attempts,
        "admitted": allowed,
        "failedOrDenied": attempts - allowed,
        "finalEventHash": previous,
        "rawArtifact": raw_artifact,
        "remoteProviderCalls": 0,
        "providerCostEur": 0,
        "paidSecretReads": False,
        "awsActions": 0,
        "hardwareAttestation": False,
        "hostTrustRequired": True,
        "confirmatoryClaimsPermitted": False,
        "completedAt": _now(),
    }
    manifest = {**core, "manifestHash": sha256_json(core)}
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return verify_local_model_admission(research_root, platform_root)


def verify_local_model_admission(
    research_root: Path, platform_root: Path
) -> dict[str, Any]:
    freeze = verify_local_admission_freeze(research_root, platform_root)
    config = _read_config(research_root)
    manifest_path = research_root / config["run_manifest_path"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed = manifest.pop("manifestHash", None)
    if not isinstance(claimed, str) or sha256_json(manifest) != claimed:
        raise ValueError("local admission run manifest self-hash mismatch")
    manifest["manifestHash"] = claimed
    if manifest["freezeManifestHash"] != freeze["freezeManifestHash"]:
        raise ValueError("local admission run is not bound to the active freeze")
    raw_path = research_root / manifest["rawArtifact"]["path"]
    if sha256_file(raw_path) != manifest["rawArtifact"]["sha256"]:
        raise ValueError("local admission raw artifact hash mismatch")
    events = read_jsonl(raw_path)
    if len(events) != manifest["attempts"] or len(events) != len(config["models"]):
        raise ValueError("local admission event count mismatch")
    previous = "0" * 64
    admitted = 0
    for sequence, (event, model) in enumerate(zip(events, config["models"], strict=True), start=1):
        event_hash = event.pop("eventHash", None)
        if event.get("previousEventHash") != previous or sha256_json(event) != event_hash:
            raise ValueError("local admission event chain mismatch")
        event["eventHash"] = event_hash
        previous = event_hash
        if event["sequence"] != sequence or event["laneId"] != model["lane_id"]:
            raise ValueError("local admission lane ordering mismatch")
        if any(
            (
                event["remoteProviderCalls"] != 0,
                event["providerCostEur"] != 0,
                event["paidSecretRead"],
                event["awsActions"] != 0,
                event["hardwareAttestation"],
                event["automaticRetries"] != 0,
                event["fallbackUsed"],
            )
        ):
            raise ValueError("local admission safety invariant failed")
        if event["status"] == "ADMITTED":
            result = event["result"]
            evidence = result["evidence"]
            release = result["nativeRelease"]
            if evidence["pinnedModelId"] != model["expected_pinned_model_id"]:
                raise ValueError("observed local model identity mismatch")
            if evidence["modelManifestHash"] != model["expected_manifest_hash"]:
                raise ValueError("observed local model manifest mismatch")
            if evidence["contractHash"] != event["contractHash"]:
                raise ValueError("local evidence contract mismatch")
            if evidence["transmittedFields"] != config["selected_fields"]:
                raise ValueError("local evidence projection mismatch")
            if evidence["hardwareAttestation"] or not evidence["hostTrustRequired"]:
                raise ValueError("local trust boundary was misrepresented")
            if not release["allowed"] or any(
                item["decision"] == "DENY" for item in release["events"]
            ):
                raise ValueError("admitted lane did not pass native release")
            json.loads(result["quarantinedOutput"])
            admitted += 1
    if previous != manifest["finalEventHash"] or admitted != manifest["admitted"]:
        raise ValueError("local admission summary mismatch")
    text = raw_path.read_text(encoding="utf-8").lower()
    if any(marker.lower() in text for marker in FORBIDDEN_SECRET_MARKERS):
        raise ValueError("provider secret marker found in local admission evidence")
    return manifest


def current_repository_bindings(research_root: Path, platform_root: Path) -> dict[str, str]:
    return {"researchCommit": git_commit(research_root), "platformCommit": git_commit(platform_root)}
