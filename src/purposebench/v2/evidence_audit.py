"""Final integrity and policy audit for the bounded phase-two evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import git_commit, read_jsonl, sha256_file, sha256_json
from purposebench.v2.frontier_matrix import committed_budget_eur
from purposebench.v2.phase_budget import committed_category_eur

PHASE_CONFIG = Path("configs/v2/openrouter-phase2.json")
REPORTS = {
    "claudeClosure": Path("results/v2/derived/openrouter-claude-closure.json"),
    "positionDiagnostic": Path(
        "results/v2/derived/openrouter-position-diagnostic.json"
    ),
    "reducedGovernedMatrix": Path(
        "results/v2/derived/openrouter-reduced-governed-matrix.json"
    ),
    "fullConditionPilot": Path(
        "results/v2/derived/openrouter-full-condition-pilot.json"
    ),
}
TRAINING_VALIDATION = Path(
    "results/v2/raw/privacy/dp-training-phase2-validation.json"
)
PRIVACY_ATTACK_VALIDATION = Path(
    "results/v2/raw/privacy/privacy-attack-phase2-validation.json"
)
PLATFORM_ATTACK_SUITE = Path(
    "results/v2/raw/platform/local-attack-suite-phase2.json"
)


def _load_json(root: Path, relative: Path | str) -> dict[str, Any]:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"evidence path is not repository-relative: {path}")
    resolved = (root / path).resolve()
    if root.resolve() not in resolved.parents or not resolved.is_file():
        raise ValueError(f"evidence artifact is absent or escaped the repository: {path}")
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"evidence artifact is not a JSON object: {path}")
    return value


def verify_self_hash(payload: Mapping[str, Any], field: str) -> str:
    """Verify a canonical self-hash and return it."""

    material = dict(payload)
    claimed = material.pop(field, None)
    actual = sha256_json(material)
    if claimed != actual:
        raise ValueError(f"{field} integrity check failed")
    return actual


def _verified_raw_artifact(
    root: Path,
    relative: str,
    claimed_hash: str,
) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("raw evidence path is not repository-relative")
    resolved = (root / path).resolve()
    if root.resolve() not in resolved.parents or not resolved.is_file():
        raise ValueError(f"raw evidence artifact is absent: {relative}")
    if sha256_file(resolved) != claimed_hash:
        raise ValueError(f"raw evidence hash mismatch: {relative}")
    return resolved


def _remote_artifact_inventory(
    root: Path,
    reports: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    references: list[tuple[str, str]] = []
    claude = reports["claudeClosure"]
    inventory = claude["failureInventory"]
    references.append(
        (inventory["currentArtifact"], inventory["currentArtifactSha256"])
    )
    for report_name in ("positionDiagnostic", "reducedGovernedMatrix"):
        for model in reports[report_name]["models"]:
            references.append((model["rawArtifact"], model["rawArtifactSha256"]))
    condition = reports["fullConditionPilot"]
    references.append((condition["rawArtifact"], condition["rawArtifactSha256"]))

    artifacts: list[dict[str, Any]] = []
    for relative, claimed_hash in references:
        path = _verified_raw_artifact(root, relative, claimed_hash)
        rows = read_jsonl(path)
        if not rows:
            raise ValueError(f"raw evidence artifact is empty: {relative}")
        artifacts.append(
            {
                "path": relative,
                "sha256": claimed_hash,
                "recordCount": len(rows),
            }
        )
    return artifacts


def _audit_remote_records(root: Path, inventory: list[dict[str, Any]]) -> dict[str, Any]:
    successes = 0
    failures = 0
    provider_calls = 0
    for artifact in inventory:
        rows = read_jsonl(root / artifact["path"])
        for row in rows:
            contract = row.get("contractMaterial")
            if not isinstance(contract, dict) or contract.get("gateway") != "OPENROUTER":
                raise ValueError("remote evidence is not bound to the OpenRouter gateway")
            if contract.get("routing") != {
                "fallbackAllowed": False,
                "providerDataCollectionAllowed": False,
                "requireParameters": True,
                "zeroDataRetentionRequired": True,
            }:
                raise ValueError("remote evidence routing policy is not fail-closed ZDR")
            if row.get("retryCount") != 0 or row.get("providerCalls") != 1:
                raise ValueError("remote evidence contains an unapproved retry/call count")
            provider_calls += 1
            status = row.get("status")
            if status == "passed":
                if row.get("releaseAllowed") is not True:
                    raise ValueError("successful remote output lacks an allow decision")
                native = row.get("nativeReleaseEvidence")
                if not isinstance(native, dict) or native.get("allowed") is not True:
                    raise ValueError("successful remote output lacks native release evidence")
                model_evidence = row.get("modelEvidence")
                if (
                    not isinstance(model_evidence, dict)
                    or model_evidence.get("destinationProvider") != "OPENROUTER"
                    or model_evidence.get("destinationHost") != "openrouter.ai"
                ):
                    raise ValueError("successful remote output used an unexpected provider")
                successes += 1
            elif status == "failed":
                if row.get("releaseAllowed") is True:
                    raise ValueError("failed remote output was marked releasable")
                if not isinstance(row.get("providerDiagnostic"), dict):
                    raise ValueError("failed remote output lacks a safe diagnostic")
                failures += 1
            else:
                raise ValueError("remote evidence contains an unknown execution status")
    return {
        "artifactCount": len(inventory),
        "recordCount": successes + failures,
        "successfulRecords": successes,
        "failedClosedRecords": failures,
        "providerCalls": provider_calls,
        "automaticRetries": 0,
        "fallbacks": 0,
        "gateway": "OPENROUTER",
        "zeroDataRetentionRequired": True,
    }


def _audit_budget(
    root: Path,
    config: Mapping[str, Any],
    condition_report: Mapping[str, Any],
) -> dict[str, Any]:
    budget = config["budget"]
    ledger = read_jsonl(root / budget["ledger"])
    committed = committed_budget_eur(ledger)
    if committed > float(budget["absoluteAuthorizedEur"]):
        raise ValueError("OpenRouter ledger exceeds the absolute authorization")
    report_budget = condition_report["budget"]
    if (
        report_budget["ledgerPrefixRecordCount"] != len(ledger)
        or report_budget["ledgerPrefixHash"] != sha256_json(ledger)
        or float(report_budget["globalCommittedEur"]) != committed
    ):
        raise ValueError("final condition report does not bind the complete budget ledger")

    authorization_id = "openrouter-phase2-user-20260805-eur5"
    phase_rows = [row for row in ledger if row.get("authorizationId") == authorization_id]
    reservations = {
        row["reservationId"]: row
        for row in phase_rows
        if row["recordType"] == "budget_reservation"
    }
    settlements = {
        row["reservationId"]: row
        for row in phase_rows
        if row["recordType"] == "budget_settlement"
    }
    if not reservations or set(reservations) != set(settlements):
        raise ValueError("phase-two budget reservations are not completely settled")

    category_spend: dict[str, float] = {}
    for category, cap in budget["categories"].items():
        spend = committed_category_eur(ledger, category)
        if spend > float(cap):
            raise ValueError(f"OpenRouter category exceeds authorization: {category}")
        category_spend[category] = spend
    prior = float(budget["priorCommittedEur"])
    additional = float(budget["additionalAuthorizedEur"])
    additional_spent = round(committed - prior, 9)
    return {
        "ledger": budget["ledger"],
        "ledgerRecordCount": len(ledger),
        "ledgerHash": sha256_json(ledger),
        "priorCommittedEur": prior,
        "additionalAuthorizedEur": additional,
        "additionalSpentEur": additional_spent,
        "additionalRemainingEur": round(additional - additional_spent, 9),
        "absoluteAuthorizedEur": float(budget["absoluteAuthorizedEur"]),
        "globalCommittedEur": committed,
        "globalRemainingEur": round(float(budget["absoluteAuthorizedEur"]) - committed, 9),
        "categoryCommittedEur": category_spend,
        "phaseReservationCount": len(reservations),
        "phaseSettlementCount": len(settlements),
    }


def build_phase2_evidence_audit(
    root: Path,
    platform_root: Path,
    secret_scan: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate committed phase-two artifacts and return a sealed audit report."""

    root = root.resolve()
    platform_root = platform_root.resolve()
    config = _load_json(root, PHASE_CONFIG)
    reports = {name: _load_json(root, path) for name, path in REPORTS.items()}
    report_hashes = {
        "claudeClosure": verify_self_hash(reports["claudeClosure"], "closureHash"),
        "positionDiagnostic": verify_self_hash(
            reports["positionDiagnostic"], "reportHash"
        ),
        "reducedGovernedMatrix": verify_self_hash(
            reports["reducedGovernedMatrix"], "reportHash"
        ),
        "fullConditionPilot": verify_self_hash(
            reports["fullConditionPilot"], "reportHash"
        ),
    }
    consent_path = Path(reports["fullConditionPilot"]["controlledExposureConsent"])
    consent = _load_json(root, consent_path)
    if verify_self_hash(consent, "consentHash") != reports["fullConditionPilot"][
        "controlledExposureConsentHash"
    ]:
        raise ValueError("controlled-exposure consent hash mismatch")

    inventory = _remote_artifact_inventory(root, reports)
    remote_execution = _audit_remote_records(root, inventory)
    budget = _audit_budget(root, config, reports["fullConditionPilot"])

    policy = config["commercialProviderPolicy"]
    expected_credential = {
        "provider": "LOCAL_ENV_REFERENCE",
        "reference": "OPENROUTER_API_KEY",
    }
    if (
        policy.get("gateway") != "OPENROUTER"
        or policy.get("credentialReference") != expected_credential
        or policy.get("directProviderApisAllowed") is not False
        or policy.get("fallbackAllowed") is not False
        or policy.get("zeroDataRetentionRequired") is not True
        or policy.get("providerDataCollectionAllowed") is not False
    ):
        raise ValueError("commercial provider policy is not OpenRouter-only and fail-closed")
    if (
        secret_scan.get("credentialReference") != expected_credential
        or secret_scan.get("trackedSecretValueHits") != 0
        or secret_scan.get("gitHistorySecretValueHits") != 0
        or secret_scan.get("keyValueRecorded") is not False
        or secret_scan.get("keyValueHashed") is not False
    ):
        raise ValueError("secret persistence audit failed")

    training = _load_json(root, TRAINING_VALIDATION)
    attacks = _load_json(root, PRIVACY_ATTACK_VALIDATION)
    training_names = {item["config_name"] for item in training["results"]}
    if training.get("status") != "passed" or training_names != {
        "non_dp",
        "weak_dp",
        "medium_dp",
        "stronger_dp",
    }:
        raise ValueError("DP training validation is incomplete")
    private_results = [item for item in training["results"] if item["private"]]
    if any(
        not isinstance(item.get("actual_epsilon"), (int, float))
        or item["actual_epsilon"] <= 0
        for item in private_results
    ):
        raise ValueError("DP training validation lacks actual accountant epsilon")
    if (
        attacks.get("status") != "passed"
        or len(attacks["measurements"]) != 15
        or len(attacks["comparisons"]) != 5
    ):
        raise ValueError("privacy-attack validation is incomplete")

    platform = _load_json(root, PLATFORM_ATTACK_SUITE)
    if (
        platform.get("status") != "passed"
        or len(platform["attacks"]) != 17
        or len(platform["gates"]) != 2
        or any(gate["exitCode"] != 0 for gate in platform["gates"])
    ):
        raise ValueError("platform attack suite did not pass")

    artifacts = {
        name: {
            "path": REPORTS[name].as_posix(),
            "sha256": sha256_file(root / REPORTS[name]),
            "selfHash": report_hashes[name],
        }
        for name in REPORTS
    }
    for name, path in {
        "dpTrainingValidation": TRAINING_VALIDATION,
        "privacyAttackValidation": PRIVACY_ATTACK_VALIDATION,
        "platformAttackSuite": PLATFORM_ATTACK_SUITE,
    }.items():
        artifacts[name] = {
            "path": path.as_posix(),
            "sha256": sha256_file(root / path),
        }

    audit: dict[str, Any] = {
        "schemaVersion": "purposebound-finance.phase2-evidence-audit.v2",
        "recordedAt": datetime.now(UTC).isoformat(),
        "status": "PASSED_WITH_RETAINED_FAILURES",
        "protocolId": "protocol-v2-local",
        "scope": "LOCAL_IMPLEMENTATION_AND_BOUNDED_REMOTE_PILOTS",
        "paperScaleComplete": False,
        "provenance": {
            "researchCommit": git_commit(root),
            "platformCommit": git_commit(platform_root),
            "platformEvidenceCommit": platform["platformCommit"],
        },
        "checks": {
            "derivedReportIntegrity": "PASSED",
            "rawArtifactIntegrity": "PASSED",
            "budgetLedgerIntegrity": "PASSED",
            "openRouterOnlyPolicy": "PASSED",
            "secretPersistence": "PASSED",
            "nativeReleaseEvidence": "PASSED",
            "dpTrainingValidation": "PASSED",
            "privacyAttackValidation": "PASSED",
            "platformAttackSuite": "PASSED",
        },
        "experiments": {
            "claudeCompatibility": reports["claudeClosure"]["status"],
            "positionDiagnostic": reports["positionDiagnostic"]["status"],
            "reducedGovernedMatrix": reports["reducedGovernedMatrix"]["status"],
            "fullConditionPilot": reports["fullConditionPilot"]["status"],
        },
        "budget": budget,
        "providerPolicy": {
            **policy,
            "secretPersistenceScan": dict(secret_scan),
        },
        "remoteExecution": remote_execution,
        "privacyValidation": {
            "trainingConfigurations": sorted(training_names),
            "privateConfigurationsWithActualEpsilon": len(private_results),
            "attackMeasurements": len(attacks["measurements"]),
            "attackComparisons": len(attacks["comparisons"]),
        },
        "platformValidation": {
            "status": platform["status"],
            "attackCount": len(platform["attacks"]),
            "gateCount": len(platform["gates"]),
        },
        "artifacts": artifacts,
        "remoteRawArtifacts": inventory,
        "limitations": [
            "This freezes a local implementation and bounded-pilot evidence snapshot, not a completed paper-scale experiment.",
            "Retained provider and rate-limit failures are evidence; they were not retried or replaced by fallback routes.",
            "The controlled condition pilot used one eight-record invocation per attempted condition and is not a population or causal estimate.",
            "The privacy-attack pilot validates measurement plumbing over controlled observations and is not a universal leakage guarantee.",
            "The trusted-host threat model excludes a malicious host administrator; hardware attestation was not deployed.",
        ],
    }
    audit["auditHash"] = sha256_json(audit)
    return audit
