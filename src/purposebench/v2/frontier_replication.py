"""Validate and summarize three governed frontier execution attempts."""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from statistics import fmean
from typing import Any

from purposebench.utils import read_jsonl, sha256_file, sha256_json
from purposebench.v2.frontier_analysis import REQUIRED_MODEL_EVIDENCE
from purposebench.v2.frontier_matrix import (
    BUDGET_LEDGER,
    committed_budget_eur,
    load_frontier_matrix,
)
from purposebench.v2.inference_pilot import (
    _pair_agreement,
    _validate_response,
    load_paired_records,
)


def _artifact_stem(slug: str, repetition: int) -> str:
    suffix = f"-rep{repetition}" if repetition > 1 else ""
    return f"openrouter-frontier-pilot{suffix}-{slug}"


def _budget_phase(repetition: int) -> str:
    return "pilot" if repetition == 1 else f"pilot_rep{repetition}"


def _replication_ledger_prefix(
    ledger_path: Path,
    ledger: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    phases = {_budget_phase(repetition) for repetition in (1, 2, 3)}
    last_settlement = max(
        (
            index
            for index, row in enumerate(ledger)
            if row.get("recordType") == "budget_settlement"
            and row.get("phase") in phases
        ),
        default=-1,
    )
    if last_settlement < 0:
        raise ValueError("frontier replication budget settlements are missing")
    record_count = last_settlement + 1
    raw_lines = ledger_path.read_bytes().splitlines(keepends=True)
    if len(raw_lines) != len(ledger):
        raise ValueError("frontier replication budget ledger framing is invalid")
    prefix = b"".join(raw_lines[:record_count])
    return ledger[:record_count], sha256(prefix).hexdigest()


def _validate_budget_settlement(
    ledger: list[dict[str, Any]],
    *,
    model_id: str,
    repetition: int,
    outcome: str,
    reservation_id: str | None = None,
    prefix_count: int | None = None,
    prefix_hash: str | None = None,
    expected_debit: float | None = None,
) -> dict[str, Any]:
    phase = _budget_phase(repetition)
    scoped = ledger if prefix_count is None else ledger[:prefix_count]
    if prefix_count is not None and (
        not 0 < prefix_count <= len(ledger) or sha256_json(scoped) != prefix_hash
    ):
        raise ValueError("frontier replication budget prefix integrity failed")
    settlements = [
        row
        for row in scoped
        if row.get("recordType") == "budget_settlement"
        and row.get("modelId") == model_id
        and row.get("phase") == phase
        and (reservation_id is None or row.get("reservationId") == reservation_id)
    ]
    if len(settlements) != 1 or settlements[0].get("outcome") != outcome:
        raise ValueError("frontier replication budget settlement is invalid")
    settlement = settlements[0]
    if expected_debit is not None and float(settlement["budgetDebitEur"]) != expected_debit:
        raise ValueError("frontier replication budget debit differs from evidence")
    reservations = [
        row
        for row in scoped
        if row.get("recordType") == "budget_reservation"
        and row.get("reservationId") == settlement["reservationId"]
    ]
    if (
        len(reservations) != 1
        or reservations[0].get("modelId") != model_id
        or reservations[0].get("phase") != phase
        or float(settlement["budgetDebitEur"])
        > float(reservations[0]["authorizedCostEur"])
    ):
        raise ValueError("frontier replication reservation is invalid")
    return settlement


def _validate_success(
    benchmark_root: Path,
    config: Mapping[str, Any],
    model: Mapping[str, Any],
    repetition: int,
    ledger: list[dict[str, Any]],
    dataset_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    stem = _artifact_stem(str(model["artifactSlug"]), repetition)
    raw_relative = Path(f"results/v2/raw/inference/{stem}.jsonl")
    manifest_relative = Path(f"results/v2/manifests/{stem}.json")
    raw_path = benchmark_root / raw_relative
    manifest_path = benchmark_root / manifest_relative
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frontier = manifest.get("frontierMatrix")
    if (
        manifest.get("schemaVersion") != "purposebound-finance.remote-pilot-manifest.v2"
        or manifest.get("status") != "passed"
        or manifest.get("attemptCount") != 1
        or manifest.get("model") != model["modelId"]
        or manifest.get("modelManifestHash") != model["manifestHash"]
        or manifest.get("repetition", 1) != repetition
        or not isinstance(frontier, dict)
        or frontier.get("phase") != "pilot"
        or frontier.get("repetition", 1) != repetition
        or frontier.get("matrixHash") != config["modelMatrixHash"]
        or manifest.get("rawArtifact") != raw_relative.as_posix()
        or manifest.get("rawArtifactSha256") != sha256_file(raw_path)
    ):
        raise ValueError("frontier replication manifest integrity failed")
    attempts = read_jsonl(raw_path)
    passed = [row for row in attempts if row.get("status") == "passed"]
    if len(attempts) != 1 or len(passed) != 1:
        raise ValueError("frontier replication must contain exactly one passing attempt")
    row = passed[0]
    if (
        row.get("repetition", 1) != repetition
        or row.get("datasetPath") != config["dataset"]
        or row.get("datasetSha256") != sha256_file(benchmark_root / config["dataset"])
        or row.get("recordCount") != 40
        or row.get("pairCount") != 20
        or row.get("completePairCount") != 20
        or row.get("releaseAllowed") is not True
        or row.get("disclosureFindings") != []
        or row.get("pinnedModelId") != model["modelId"]
        or row.get("modelManifestHash") != model["manifestHash"]
        or row.get("modelProvider") != "OPENROUTER"
    ):
        raise ValueError("frontier replication release or model evidence failed")
    evidence = row.get("modelEvidence")
    if not isinstance(evidence, dict) or not REQUIRED_MODEL_EVIDENCE.issubset(evidence):
        raise ValueError("frontier replication model evidence is incomplete")
    case_ids = [str(item["case_id"]) for item in dataset_rows]
    output = row["quarantinedOutput"]
    normalized = _validate_response(
        json.loads(output) if isinstance(output, str) else output,
        case_ids,
    )
    if sha256_json(normalized) != row.get("normalizedResultsHash"):
        raise ValueError("frontier replication normalized output integrity failed")
    metrics = _pair_agreement(normalized, dataset_rows)
    recorded_metrics = row.get("pairMetrics")
    if not isinstance(recorded_metrics, dict) or any(
        recorded_metrics.get(key) != metrics[key]
        for key in ("pairs", "decisionAgreements", "decisionAgreementRate")
    ):
        raise ValueError("frontier replication pair metrics differ from raw evidence")
    contract = dict(row["contractMaterial"])
    if repetition == 1:
        if "repetition" in contract:
            raise ValueError("original frontier pilot unexpectedly binds a repetition")
    elif contract.pop("repetition", None) != repetition:
        raise ValueError("frontier replication is not contract-bound")
    budget = manifest.get("budget")
    if not isinstance(budget, dict) or budget.get("ledgerArtifact") != BUDGET_LEDGER.as_posix():
        raise ValueError("frontier replication budget evidence is missing")
    _validate_budget_settlement(
        ledger,
        model_id=str(model["modelId"]),
        repetition=repetition,
        outcome="passed",
        reservation_id=str(budget["reservationId"]),
        prefix_count=int(budget["ledgerPrefixRecordCount"]),
        prefix_hash=str(budget["ledgerPrefixHash"]),
        expected_debit=float(row["budgetDebitEur"]),
    )
    decisions = [str(item["decision"]) for item in normalized]
    risk_scores = [float(item["risk_score"]) for item in normalized]
    provider_cost = evidence.get("providerReportedCost") or {}
    return {
        "repetition": repetition,
        "status": "PASSED",
        "rawArtifact": raw_relative.as_posix(),
        "rawArtifactSha256": sha256_file(raw_path),
        "manifestArtifact": manifest_relative.as_posix(),
        "manifestArtifactSha256": sha256_file(manifest_path),
        "durationSeconds": row["durationSeconds"],
        "conservativeDebitEur": row["budgetDebitEur"],
        "providerReportedCostOpenRouterCredits": provider_cost.get("amount"),
        "normalizedResultsHash": row["normalizedResultsHash"],
        "contractMaterialWithoutRepetitionHash": sha256_json(contract),
        "transmittedRecordHash": row["transmittedRecordHash"],
        "pairMetrics": metrics,
        "recordedPairMetrics": recorded_metrics,
        "decisions": decisions,
        "riskScores": risk_scores,
    }


def _validate_failure(
    benchmark_root: Path,
    model: Mapping[str, Any],
    repetition: int,
    ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    stem = _artifact_stem(str(model["artifactSlug"]), repetition)
    relative = Path(f"results/v2/raw/inference/{stem}.jsonl.partial")
    path = benchmark_root / relative
    attempts = read_jsonl(path)
    if len(attempts) != 1 or attempts[0].get("status") != "failed":
        raise ValueError("frontier failed replication cardinality is invalid")
    row = attempts[0]
    if (
        row.get("repetition") != repetition
        or row.get("pinnedModelId") != model["modelId"]
        or row.get("modelManifestHash") != model["manifestHash"]
        or row.get("modelProvider") != "OPENROUTER"
        or float(row.get("budgetDebitEur", -1)) != 0.25
    ):
        raise ValueError("frontier failed replication evidence is invalid")
    settlement = _validate_budget_settlement(
        ledger,
        model_id=str(model["modelId"]),
        repetition=repetition,
        outcome="failed_conservative_debit",
        expected_debit=0.25,
    )
    return {
        "repetition": repetition,
        "status": "FAILED_CLOSED",
        "rawArtifact": relative.as_posix(),
        "rawArtifactSha256": sha256_file(path),
        "errorType": row.get("errorType"),
        "error": row.get("error"),
        "conservativeDebitEur": settlement["budgetDebitEur"],
    }


def build_frontier_replication_report(
    benchmark_root: Path,
    config_path: Path,
) -> dict[str, Any]:
    config, models = load_frontier_matrix(benchmark_root, config_path.resolve())
    dataset_path = (benchmark_root / config["dataset"]).resolve()
    dataset_rows = load_paired_records(dataset_path, pair_limit=20)
    if len(dataset_rows) != 40:
        raise ValueError("frontier replication requires exactly 40 records")
    ledger_path = benchmark_root / BUDGET_LEDGER
    ledger = read_jsonl(ledger_path)
    replication_ledger, replication_ledger_hash = _replication_ledger_prefix(
        ledger_path,
        ledger,
    )
    model_results: list[dict[str, Any]] = []
    successful_attempts = 0
    failed_attempts = 0
    replication_debit = 0.0
    known_provider_cost = 0.0
    successful_pair_observations = 0
    influenced_pair_observations = 0
    successful_attempts_with_influence = 0

    for model in models:
        slug = str(model["artifactSlug"])
        base_raw = benchmark_root / f"results/v2/raw/inference/{_artifact_stem(slug, 1)}.jsonl"
        if not base_raw.exists():
            model_results.append(
                {
                    "modelId": model["modelId"],
                    "status": "INELIGIBLE_SMOKE_GATE",
                    "plannedAttempts": 0,
                    "successfulAttempts": 0,
                    "failedAttempts": 0,
                }
            )
            continue

        attempts: list[dict[str, Any]] = []
        passed: list[dict[str, Any]] = []
        for repetition in (1, 2, 3):
            stem = _artifact_stem(slug, repetition)
            final_path = benchmark_root / f"results/v2/raw/inference/{stem}.jsonl"
            partial_path = benchmark_root / f"results/v2/raw/inference/{stem}.jsonl.partial"
            if final_path.exists() and not partial_path.exists():
                attempt = _validate_success(
                    benchmark_root,
                    config,
                    model,
                    repetition,
                    ledger,
                    dataset_rows,
                )
                passed.append(attempt)
                successful_attempts += 1
                pair_metrics = attempt["pairMetrics"]
                successful_pair_observations += int(pair_metrics["pairs"])
                influenced_pair_observations += int(pair_metrics["pairedInfluences"])
                successful_attempts_with_influence += (
                    float(pair_metrics["pairedInfluenceRate"]) > 0
                )
                known_provider_cost += float(
                    attempt["providerReportedCostOpenRouterCredits"] or 0
                )
            elif partial_path.exists() and not final_path.exists():
                attempt = _validate_failure(
                    benchmark_root,
                    model,
                    repetition,
                    ledger,
                )
                failed_attempts += 1
            else:
                raise ValueError("frontier replication artifact state is incomplete or ambiguous")
            replication_debit += float(attempt["conservativeDebitEur"])
            attempts.append(attempt)

        contract_hashes = {
            str(item["contractMaterialWithoutRepetitionHash"])
            for item in passed
        }
        transmitted_hashes = {str(item["transmittedRecordHash"]) for item in passed}
        if len(contract_hashes) != 1 or len(transmitted_hashes) != 1:
            raise ValueError("frontier repetitions changed approved execution material")
        decisions_by_record = list(zip(*(item["decisions"] for item in passed), strict=True))
        scores_by_record = list(zip(*(item["riskScores"] for item in passed), strict=True))
        decision_stable = sum(len(set(values)) == 1 for values in decisions_by_record)
        score_stable = sum(len(set(values)) == 1 for values in scores_by_record)
        score_ranges = [max(values) - min(values) for values in scores_by_record]
        model_results.append(
            {
                "modelId": model["modelId"],
                "canonicalSlug": model["canonicalSlug"],
                "providerRoute": model["providerRouting"]["only"][0],
                "status": "COMPLETE_WITH_FAILURES" if len(passed) < 3 else "COMPLETE",
                "plannedAttempts": 3,
                "successfulAttempts": len(passed),
                "failedAttempts": 3 - len(passed),
                "attempts": attempts,
                "stabilityAcrossSuccessfulAttempts": {
                    "comparedAttempts": len(passed),
                    "decisionExactAgreementRecords": decision_stable,
                    "decisionExactAgreementRate": decision_stable / 40,
                    "riskScoreExactAgreementRecords": score_stable,
                    "riskScoreExactAgreementRate": score_stable / 40,
                    "meanRiskScoreRange": fmean(score_ranges),
                    "maximumRiskScoreRange": max(score_ranges),
                },
                "decisionCountsByAttempt": [
                    dict(sorted(Counter(item["decisions"]).items())) for item in passed
                ],
            }
        )

    return finalize_frontier_replication_report(
        {
            "schemaVersion": "purposebound-finance.frontier-replication.v2",
            "matrixHash": config["modelMatrixHash"],
            "dataset": config["dataset"],
            "datasetSha256": sha256_file(dataset_path),
            "plannedAttemptsPerEligibleModel": 3,
            "eligibleModelCount": sum(
                item["status"] != "INELIGIBLE_SMOKE_GATE" for item in model_results
            ),
            "configuredModelCount": len(models),
            "plannedAttempts": 3
            * sum(item["status"] != "INELIGIBLE_SMOKE_GATE" for item in model_results),
            "successfulAttempts": successful_attempts,
            "failedClosedAttempts": failed_attempts,
            "pairedPurpose": {
                "successfulPairObservations": successful_pair_observations,
                "influencedPairObservations": influenced_pair_observations,
                "successfulAttemptsWithInfluence": successful_attempts_with_influence,
                "successfulAttemptsWithoutInfluence": (
                    successful_attempts - successful_attempts_with_influence
                ),
            },
            "models": model_results,
            "budget": {
                "authorizedEur": config["totalAuthorizedCostEur"],
                "committedEur": committed_budget_eur(replication_ledger),
                "remainingEur": round(
                    float(config["totalAuthorizedCostEur"])
                    - committed_budget_eur(replication_ledger),
                    9,
                ),
                "threeAttemptConservativeDebitEur": round(replication_debit, 9),
                "threeAttemptKnownProviderCostOpenRouterCredits": round(
                    known_provider_cost,
                    9,
                ),
                "budgetLedger": BUDGET_LEDGER.as_posix(),
                "budgetLedgerSha256": replication_ledger_hash,
                "failedCallsWithoutCostEvidenceRemainFullyDebited": True,
            },
            "limitations": [
                "This is a 40-record governed remote replication, not a full condition matrix or population estimate.",
                "Stability metrics compare successful outputs only; failed calls remain visible separately.",
                "A deterministic decision does not imply a calibrated or correct risk score.",
                "Claude is excluded because no strict ZDR smoke gate passed.",
                "Remote processing occurred through OpenRouter under pinned ZDR routes.",
            ],
            "reportHash": "",
        }
    )


def finalize_frontier_replication_report(value: dict[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("reportHash", None)
    value["reportHash"] = sha256_json(material)
    return value


def write_frontier_replication_report(
    benchmark_root: Path,
    report: dict[str, Any],
) -> dict[str, Path]:
    derived_path = benchmark_root / "results/v2/derived/openrouter-frontier-replication.json"
    derived_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = derived_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, derived_path)

    report_path = benchmark_root / "docs/v2/FRONTIER_REPLICATION_RESULTS.md"
    lines = [
        "# Governed frontier replication results",
        "",
        "Five admitted frontier models received three planned forty-record executions each.",
        "Outputs were released only after native validation; failures remained fail-closed.",
        "",
        "| Model | Passed | Failed | Decision stability | Risk-score stability | Mean score range |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model in report["models"]:
        if model["status"] == "INELIGIBLE_SMOKE_GATE":
            lines.append(f"| `{model['modelId']}` | 0 | 0 | excluded | excluded | excluded |")
            continue
        stability = model["stabilityAcrossSuccessfulAttempts"]
        lines.append(
            f"| `{model['modelId']}` | {model['successfulAttempts']} | "
            f"{model['failedAttempts']} | {stability['decisionExactAgreementRate']:.3f} | "
            f"{stability['riskScoreExactAgreementRate']:.3f} | "
            f"{stability['meanRiskScoreRange']:.3f} |"
        )
    lines.extend(
        (
            "",
            "## Attempt-level paired-purpose result",
            "",
            "| Model | Repetition | Result | Paired influence |",
            "| --- | ---: | --- | ---: |",
        )
    )
    for model in report["models"]:
        for attempt in model.get("attempts", []):
            if attempt["status"] == "PASSED":
                result = "released"
                influence = f"{attempt['pairMetrics']['pairedInfluences']}/20"
            else:
                result = f"failed closed (`{attempt['errorType']}`)"
                influence = "not released"
            lines.append(
                f"| `{model['modelId']}` | {attempt['repetition']} | {result} | {influence} |"
            )
    paired = report["pairedPurpose"]
    lines.extend(
        (
            "",
            (
                f"One of {report['successfulAttempts']} released attempts had paired influence: "
                f"{paired['influencedPairObservations']} of "
                f"{paired['successfulPairObservations']} successful pair observations overall."
            ),
            (
                "The affected GPT-5.6 Luna repetition changed decisions for identical approved "
                "projections; its risk scores stayed equal within each pair. Because the "
                "transmitted record hash was unchanged and prohibited fields were absent, this "
                "is evidence of execution instability rather than evidence that prohibited "
                "fields were used."
            ),
        )
    )
    budget = report["budget"]
    lines.extend(
        (
            "",
            "## Execution and budget",
            "",
            f"- Planned attempts: {report['plannedAttempts']}.",
            f"- Passed: {report['successfulAttempts']}; failed closed: {report['failedClosedAttempts']}.",
            f"- Conservative three-attempt debit: EUR {budget['threeAttemptConservativeDebitEur']}.",
            f"- Cumulative conservative ledger: EUR {budget['committedEur']} of EUR {budget['authorizedEur']}.",
            f"- Remaining authorization: EUR {budget['remainingEur']}.",
            "",
            "## Interpretation boundary",
            "",
        )
    )
    lines.extend(f"- {item}" for item in report["limitations"])
    report_temp = report_path.with_suffix(".md.tmp")
    report_temp.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    os.replace(report_temp, report_path)
    return {"derived": derived_path, "report": report_path}
