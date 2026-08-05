"""Protocol-v3 configuration validation and dry-run freeze helpers."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from purposebench.utils import (
    canonical_json,
    git_provenance,
    sha256_file,
    sha256_json,
)
from purposebench.v3.attacks import ATTACK_REGISTRY

EXPECTED_CONDITIONS = (
    "B0",
    "B1",
    "B2",
    "P0",
    "P1",
    "P2",
    "P3",
    "D0",
    "D1",
    "D2",
    "D3",
)
EXPECTED_INFERENCE_CONDITIONS = EXPECTED_CONDITIONS[:7]
EXPECTED_PRIVACY_CONDITIONS = EXPECTED_CONDITIONS[7:]
HASH_PATTERN = re.compile(r"^[a-f0-9]{64}$")
GIT_COMMIT_PATTERN = re.compile(r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a mapping")
    return value


def validate_protocol_design(root: Path) -> dict[str, Any]:
    path = root / "configs/v3/protocol-v3-psbe-no-tee.yaml"
    protocol = load_yaml(path)
    if protocol.get("protocol_id") != "protocol-v3-psbe-no-tee":
        raise ValueError("unexpected protocol ID")
    conditions = tuple(item["id"] for item in protocol.get("conditions", []))
    if conditions != EXPECTED_CONDITIONS:
        raise ValueError(f"condition order changed: {conditions}")
    configured_attacks = tuple(
        attack_id
        for family in protocol.get("attack_families", {}).values()
        for attack_id in family.get("ids", [])
    )
    registered_attacks = tuple(item.attack_id for item in ATTACK_REGISTRY)
    if configured_attacks != registered_attacks:
        raise ValueError("protocol attack IDs differ from the executable registry")
    if protocol.get("cost", {}).get("paid_authorization_recorded") is not False:
        raise ValueError("paid authorization must remain false before paid readiness")
    if protocol.get("tee_extension", {}).get("aws_actions_authorized") is not False:
        raise ValueError("AWS actions are not authorized")
    return protocol


def validate_dry_run_config(root: Path) -> dict[str, Any]:
    validate_protocol_design(root)
    config = load_yaml(root / "configs/v3/dry-run-v3.yaml")
    if config.get("scope") != "INSTRUMENTATION_ONLY_NO_COST_NON_TEE":
        raise ValueError("dry-run scope is not instrumentation-only")
    if tuple(config.get("conditions", [])) != EXPECTED_CONDITIONS:
        raise ValueError("dry-run condition matrix changed")
    if tuple(config.get("inference_conditions", [])) != EXPECTED_INFERENCE_CONDITIONS:
        raise ValueError("dry-run inference condition matrix changed")
    if tuple(config.get("privacy_conditions", [])) != EXPECTED_PRIVACY_CONDITIONS:
        raise ValueError("dry-run privacy condition matrix changed")
    if config.get("provider_calls_permitted") != 0:
        raise ValueError("dry run permits provider calls")
    if config.get("paid_secrets_permitted") is not False:
        raise ValueError("dry run permits paid secrets")
    if config.get("hardware_attestation") is not False:
        raise ValueError("non-TEE dry run makes an attestation claim")
    if config.get("confirmatory_result_claims_permitted") is not False:
        raise ValueError("dry run permits confirmatory result claims")
    if config.get("development_pairs_per_dataset") != 20:
        raise ValueError("dry-run pair count changed")
    if config.get("repetitions") != 3:
        raise ValueError("dry-run repetition count changed")
    models = config.get("test_double_models", [])
    if len(models) != 3:
        raise ValueError("dry run requires exactly three test-double models")
    for model in models:
        behavior_hash = sha256_json(model["behavior"])
        expected_id = f"test-double/{model['behavior']['name']}@sha256:{behavior_hash}"
        if model.get("immutable_id") != expected_id:
            raise ValueError(f"test-double model digest mismatch for {expected_id}")
    for source in config.get("source_assets", []):
        source_path = root / source["path"]
        if not source_path.is_file() or sha256_file(source_path) != source["sha256"]:
            raise ValueError(f"source asset mismatch: {source_path}")
    return config


def freeze_manifest_hash(manifest: dict[str, Any]) -> str:
    material = dict(manifest)
    material.pop("freezeManifestHash", None)
    return sha256_json(material)


def verify_dry_run_freeze(root: Path, platform_root: Path) -> dict[str, Any]:
    config = validate_dry_run_config(root)
    path = root / config["freeze_manifest_path"]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != "finboundbench.dry-run-freeze.v3":
        raise ValueError("dry-run freeze schema is invalid")
    if manifest.get("status") != "FROZEN_INSTRUMENTATION_ONLY":
        raise ValueError("dry-run freeze is not active")
    if freeze_manifest_hash(manifest) != manifest.get("freezeManifestHash"):
        raise ValueError("dry-run freeze self-hash is invalid")
    bindings = manifest["repositoryBindings"]
    if not _is_ancestor(root, bindings["researchCommit"]):
        raise ValueError("research HEAD does not descend from the dry-run freeze")
    if not _is_ancestor(platform_root, bindings["platformCommit"]):
        raise ValueError("platform HEAD does not descend from the dry-run freeze")
    for artifact in manifest["artifacts"]:
        artifact_root = platform_root if artifact["repository"] == "platform" else root
        artifact_path = artifact_root / artifact["path"]
        if (
            not artifact_path.is_file()
            or artifact_path.stat().st_size != artifact["bytes"]
            or sha256_file(artifact_path) != artifact["sha256"]
        ):
            raise ValueError(f"frozen artifact mismatch: {artifact_path}")
    if manifest.get("paidProviderCallsPermitted") != 0:
        raise ValueError("freeze manifest permits paid provider calls")
    return manifest


def _is_ancestor(root: Path, commit: str) -> bool:
    if not GIT_COMMIT_PATTERN.fullmatch(commit):
        return False
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )


def build_dry_run_freeze_manifest(
    root: Path,
    platform_root: Path,
    *,
    research_commit: str,
    platform_commit: str,
) -> dict[str, Any]:
    """Build a manifest that binds the committed dry-run code, never outcomes."""

    validate_dry_run_config(root)
    research_paths = [
        "configs/v3/protocol-v3-psbe-no-tee.yaml",
        "configs/v3/dry-run-v3.yaml",
        "docs/v3/FORMAL_PSBE_DEFINITION.md",
        "docs/v3/FINBOUNDBENCH_SPEC.md",
        "docs/v3/HYPOTHESES.md",
        "docs/v3/STATISTICAL_PLAN.md",
        "docs/v3/COST_PLAN.md",
        "docs/v3/IMPLEMENTATION_AUDIT.md",
        "src/purposebench/v3/attacks.py",
        "src/purposebench/v3/protocol.py",
        "src/purposebench/v3/dry_run.py",
        "scripts/run_v3_no_cost_dry_run.py",
        "scripts/verify_v3_no_cost_dry_run.py",
        "paper/generated/results_placeholder.tex",
        "paper/generated/claim_traceability.csv",
    ]
    platform_paths = [
        "services/api/src/confidential-execution/evidence-v3/evidence-semantic-verifier.ts",
        "services/api/test/unit/v3/evidence-semantic-verifier.spec.ts",
    ]
    artifacts = []
    for repository, repository_root, paths in (
        ("research", root, research_paths),
        ("platform", platform_root, platform_paths),
    ):
        for relative in paths:
            path = repository_root / relative
            if not path.is_file():
                raise ValueError(f"freeze input is missing: {path}")
            artifacts.append(
                {
                    "repository": repository,
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "schemaVersion": "finboundbench.dry-run-freeze.v3",
        "status": "FROZEN_INSTRUMENTATION_ONLY",
        "scope": "NO_COST_NON_TEE_TEST_DOUBLES_NO_RESEARCH_CLAIMS",
        "protocolId": "protocol-v3-psbe-no-tee",
        "dryRunId": "protocol-v3-psbe-no-tee-dry-run",
        "frozenAt": "2026-08-05T12:00:00.000Z",
        "repositoryBindings": {
            "researchCommit": research_commit,
            "platformCommit": platform_commit,
        },
        "repositoryStateAtFreeze": {
            "research": git_provenance(root),
            "platform": git_provenance(platform_root),
            "platformScopeBoundByArtifactHashes": True,
            "unrelatedUserChangesIncluded": False,
        },
        "paidProviderCallsPermitted": 0,
        "providerSecretPermitted": False,
        "awsActionsPermitted": False,
        "hardwareAttestation": False,
        "confirmatoryClaimsPermitted": False,
        "artifacts": artifacts,
        "freezeManifestHash": "",
    }
    manifest["freezeManifestHash"] = freeze_manifest_hash(manifest)
    canonical_json(manifest)
    return manifest
