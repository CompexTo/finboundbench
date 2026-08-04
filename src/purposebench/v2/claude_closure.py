"""Build reproducible evidence for formally closing the Claude/OpenRouter lane."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from purposebench.utils import read_jsonl, sha256_file, sha256_json
from purposebench.v2.claude_compatibility import (
    BUDGET_CATEGORY,
    _effective_phase2_provider_calls,
    _passed_gate_manifest,
    load_phase_configuration,
)
from purposebench.v2.frontier_matrix import committed_budget_eur
from purposebench.v2.phase_budget import committed_category_eur


def _last_commit_for_path(root: Path, path: Path) -> str:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", path.relative_to(root).as_posix()],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    commit = result.stdout.strip()
    if len(commit) != 40:
        raise ValueError("Claude failure evidence has no immutable Git commit")
    return commit


def build_claude_closure_report(root: Path, config_path: Path) -> dict[str, Any]:
    config = load_phase_configuration(root, config_path)
    compatibility = config["claudeCompatibility"]
    gate0_path = root / "results/v2/manifests/openrouter-claude-gate0-recheck-20260805.json"
    gate0 = json.loads(gate0_path.read_text(encoding="utf-8"))
    if gate0.get("status") != "PASSED" or gate0.get("providerCalls") != 0:
        raise ValueError("Claude Gate 0 evidence is invalid")
    if _passed_gate_manifest(root, 1) is not None:
        raise ValueError("Claude lane cannot close after a passing Gate 1")

    current_paths = sorted(
        (root / "results/v2/raw/inference").glob(
            "openrouter-phase2-claude-gate1-provider-attempt*.jsonl.partial"
        )
    )
    if len(current_paths) != 1:
        raise ValueError("Claude closure requires exactly one new provider attempt")
    current_path = current_paths[0]
    current_rows = read_jsonl(current_path)
    if len(current_rows) != 1:
        raise ValueError("Claude Gate 1 failure evidence is ambiguous")
    current = current_rows[0]
    diagnostic = current.get("providerDiagnostic", {})
    if (
        current.get("status") != "failed"
        or current.get("gate") != 1
        or current.get("providerCalls") != 1
        or current.get("retryCount") != 0
        or diagnostic.get("category") != "PROVIDER_ROUTING"
        or diagnostic.get("selectedProviderRoute") != "amazon-bedrock"
        or not isinstance(diagnostic.get("responseBodySha256"), str)
    ):
        raise ValueError("Claude Gate 1 did not fail under the approved closed contract")

    prior_paths = sorted(
        (root / "results/v2/raw/inference").glob(
            "openrouter-frontier-smoke-anthropic-claude-*.jsonl.partial"
        )
    )
    prior_rows = [row for path in prior_paths for row in read_jsonl(path)]
    if len(prior_rows) != 13 or any(row.get("status") != "failed" for row in prior_rows):
        raise ValueError("Prior Claude failure inventory changed")
    fingerprint = diagnostic["responseBodySha256"]
    matching_prior_failures = sum(fingerprint in str(row.get("error", "")) for row in prior_rows)
    if matching_prior_failures < 1:
        raise ValueError("Current Claude routing failure is not corroborated by prior evidence")

    provider_calls = _effective_phase2_provider_calls(root)
    if provider_calls != 1:
        raise ValueError("Claude phase-two provider-call inventory changed")
    ledger_path = root / config["budget"]["ledger"]
    ledger = read_jsonl(ledger_path)
    report = {
        "schemaVersion": "purposebound-finance.claude-closure.v2",
        "status": "FORMALLY_CLOSED",
        "closedAt": current["finishedAt"],
        "closureReason": "NO_TESTED_CLAUDE_OPENROUTER_COMBINATION_SATISFIED_EXECUTION_CONTRACT",
        "decision": "NO_ADDITIONAL_CLAUDE_ATTEMPT_WITHOUT_NEW_MATERIAL_METADATA",
        "evidenceCommit": _last_commit_for_path(root, current_path),
        "selectedCandidate": {
            "modelId": current["contractMaterial"]["modelId"],
            "canonicalCatalogSlug": current["contractMaterial"]["canonicalCatalogSlug"],
            "route": diagnostic["selectedProviderRoute"],
            "modelManifestHash": current["modelManifestHash"],
            "contractHash": current["contractHash"],
        },
        "gates": {
            "gate0": "PASSED_LOCAL_ONLY",
            "gate1": "FAILED_CLOSED_PROVIDER_ROUTING",
            "gate2": "NOT_RUN_GATE1_REQUIRED",
            "gate3": "NOT_RUN_GATE2_REQUIRED",
            "gate4": "NOT_RUN_POSITION_DIAGNOSTIC_REQUIRED",
        },
        "newAuthorization": {
            "maximumProviderAttempts": int(compatibility["maximumSmokeAttempts"]),
            "providerCallsMade": provider_calls,
            "automaticRetries": 0,
            "fallbacks": 0,
            "unusedAttemptCapacity": int(compatibility["maximumSmokeAttempts"])
            - provider_calls,
            "unusedAttemptsAreNotARequirement": True,
        },
        "failureInventory": {
            "priorFailureCount": len(prior_rows),
            "newFailureCount": 1,
            "totalDocumentedFailures": len(prior_rows) + 1,
            "matchingPriorRoutingFingerprints": matching_prior_failures,
            "safeResponseBodySha256": fingerprint,
            "priorArtifacts": [
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256_file(path),
                    "failureCount": len(read_jsonl(path)),
                }
                for path in prior_paths
            ],
            "currentArtifact": current_path.relative_to(root).as_posix(),
            "currentArtifactSha256": sha256_file(current_path),
        },
        "budget": {
            "ledger": config["budget"]["ledger"],
            "ledgerPrefixRecordCount": len(ledger),
            "ledgerPrefixHash": sha256_json(ledger),
            "globalCommittedEur": committed_budget_eur(ledger),
            "categoryCommittedEur": committed_category_eur(ledger, BUDGET_CATEGORY),
            "categoryAuthorizedEur": compatibility["maximumCompatibilityBudgetEur"],
            "absoluteAuthorizedEur": config["budget"]["absoluteAuthorizedEur"],
        },
        "providerPolicy": {
            "gateway": "OPENROUTER",
            "directAnthropicApiUsed": False,
            "credentialReference": "OPENROUTER_API_KEY",
            "routePinned": True,
            "fallbackAllowed": False,
            "zeroDataRetentionRequired": True,
        },
        "remainingExperimentPolicy": {
            "claudeEligible": False,
            "continueWithEligibleModels": True,
            "eligibleModelIds": [
                "openai/gpt-5.6-luna",
                "deepseek/deepseek-v4-pro",
                "google/gemma-4-26b-a4b-it",
                "moonshotai/kimi-k3",
                "meta-llama/llama-4-maverick",
            ],
        },
        "closureHash": "",
    }
    material = dict(report)
    material.pop("closureHash")
    report["closureHash"] = sha256_json(material)
    return report

