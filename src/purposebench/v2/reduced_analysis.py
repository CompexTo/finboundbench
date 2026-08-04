"""Reproduce governed reduced-matrix results from raw OpenRouter evidence."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from statistics import fmean
from typing import Any

from purposebench.utils import read_jsonl, sha256_file, sha256_json
from purposebench.v2.frontier_matrix import committed_budget_eur
from purposebench.v2.inference_pilot import load_paired_records
from purposebench.v2.phase_budget import committed_category_eur
from purposebench.v2.reduced_matrix import REDUCED_CATEGORY, load_reduced_context


def _assessment_map(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    case_ids = row["orderedCaseIds"]
    assessments = row["governedActionBatch"]["assessments"]
    if len(case_ids) != 40 or len(assessments) != 40:
        raise ValueError("reduced matrix assessment count changed")
    result = {}
    for assessment in assessments:
        index = assessment["index"]
        if not isinstance(index, int) or not 0 <= index < 40:
            raise ValueError("reduced matrix index is invalid")
        result[str(case_ids[index])] = assessment
    if len(result) != 40:
        raise ValueError("reduced matrix case mapping is incomplete")
    return result


def _successful_model_metrics(
    rows: list[dict[str, Any]],
    pair_map: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    matrix_rows = sorted(
        (row for row in rows if row["matrixStage"] == "matrix"),
        key=lambda row: int(row["repetition"]),
    )
    if len(matrix_rows) != 2:
        raise ValueError("reduced matrix requires two passing repetitions")
    attempts = [_assessment_map(row) for row in matrix_rows]
    case_ids = list(attempts[0])
    if set(case_ids) != set(attempts[1]):
        raise ValueError("reduced matrix repetitions changed cases")
    exact_scores = sum(
        attempts[0][case_id]["normalizedRiskScore"]
        == attempts[1][case_id]["normalizedRiskScore"]
        for case_id in case_ids
    )
    exact_actions = sum(
        attempts[0][case_id]["governedAction"]
        == attempts[1][case_id]["governedAction"]
        for case_id in case_ids
    )
    exact_recommendations = sum(
        attempts[0][case_id]["rawRecommendation"]
        == attempts[1][case_id]["rawRecommendation"]
        for case_id in case_ids
    )
    score_ranges = [
        abs(
            attempts[0][case_id]["normalizedRiskScore"]
            - attempts[1][case_id]["normalizedRiskScore"]
        )
        for case_id in case_ids
    ]
    pair_metrics = []
    for repetition, assessments in enumerate(attempts, start=1):
        action_influences = 0
        score_differences = 0
        for case_a, case_b in pair_map.values():
            action_influences += (
                assessments[case_a]["governedAction"]
                != assessments[case_b]["governedAction"]
            )
            score_differences += (
                assessments[case_a]["normalizedRiskScore"]
                != assessments[case_b]["normalizedRiskScore"]
            )
        pair_metrics.append(
            {
                "repetition": repetition,
                "pairs": len(pair_map),
                "governedActionInfluencedPairs": action_influences,
                "governedActionInfluenceRate": action_influences / len(pair_map),
                "scoreDifferentPairs": score_differences,
                "scoreDifferenceRate": score_differences / len(pair_map),
            }
        )
    disagreements = [
        assessment["recommendationPolicyDisagreement"]
        for attempt in attempts
        for assessment in attempt.values()
        if assessment["recommendationPolicyDisagreement"] is not None
    ]
    return {
        "repetitionStability": {
            "comparedRecords": 40,
            "scoreExactAgreementRecords": exact_scores,
            "scoreExactAgreementRate": exact_scores / 40,
            "governedActionExactAgreementRecords": exact_actions,
            "governedActionExactAgreementRate": exact_actions / 40,
            "rawRecommendationExactAgreementRecords": exact_recommendations,
            "rawRecommendationExactAgreementRate": exact_recommendations / 40,
            "meanAbsoluteScoreDifference": fmean(score_ranges),
            "maximumAbsoluteScoreDifference": max(score_ranges),
        },
        "pairedPurpose": pair_metrics,
        "recommendationPolicyDisagreement": {
            "eligibleObservations": len(disagreements),
            "disagreementCount": sum(disagreements),
            "disagreementRate": (
                sum(disagreements) / len(disagreements) if disagreements else None
            ),
        },
        "attemptMaps": attempts,
    }


def build_reduced_matrix_report(root: Path) -> dict[str, Any]:
    config, manifests = load_reduced_context(
        root,
        root / "configs/v2/openrouter-phase2.json",
    )
    dataset = load_paired_records(root / config["dataset"], pair_limit=20)
    pair_map = {
        str(row["pair_id"]): (
            next(str(item["case_id"]) for item in dataset if item["pair_id"] == row["pair_id"] and item["variant"] == "A"),
            next(str(item["case_id"]) for item in dataset if item["pair_id"] == row["pair_id"] and item["variant"] == "B"),
        )
        for row in dataset
    }
    models = []
    successful_maps: dict[str, list[dict[str, dict[str, Any]]]] = {}
    matrix_reservation_ids: set[str] = set()
    for model_id in config["eligibleReducedMatrix"]["modelIds"]:
        manifest = manifests[model_id]
        slug = manifest["artifactSlug"]
        final_path = root / f"results/v2/raw/inference/openrouter-phase2-reduced-{slug}.jsonl"
        partial_path = final_path.with_suffix(".jsonl.partial")
        manifest_path = root / f"results/v2/manifests/openrouter-phase2-reduced-{slug}.json"
        if final_path.exists() and not partial_path.exists():
            rows = read_jsonl(final_path)
            result_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                len(rows) != 3
                or result_manifest.get("status") != "PASSED"
                or result_manifest.get("rawArtifactSha256") != sha256_file(final_path)
                or any(
                    row.get("status") != "passed"
                    or row.get("releaseAllowed") is not True
                    or row.get("providerCalls") != 1
                    or row.get("retryCount") != 0
                    or row.get("prohibitedSyntheticFieldsTransmitted") is not False
                    or row.get("modelManifestHash") != manifest["manifestHash"]
                    or row.get("contractMaterial", {}).get("actionPolicyHash")
                    != config["actionPolicyHash"]
                    for row in rows
                )
            ):
                raise ValueError("passing reduced matrix evidence is invalid")
            metrics = _successful_model_metrics(rows, pair_map)
            matrix_reservation_ids.update(
                str(row["budget"]["reservationId"]) for row in rows
            )
            successful_maps[model_id] = metrics.pop("attemptMaps")
            models.append(
                {
                    "modelId": model_id,
                    "status": "PASSED",
                    "rawArtifact": final_path.relative_to(root).as_posix(),
                    "rawArtifactSha256": sha256_file(final_path),
                    "providerCalls": 3,
                    "retryCount": 0,
                    "conservativeDebitEur": sum(
                        float(row["budget"]["conservativeDebitEur"]) for row in rows
                    ),
                    **metrics,
                    "eligibleForFullConditionPilot": True,
                }
            )
        elif partial_path.exists() and not final_path.exists() and not manifest_path.exists():
            rows = read_jsonl(partial_path)
            if (
                len(rows) != 2
                or rows[0].get("status") != "passed"
                or rows[0].get("matrixStage") != "smoke"
                or rows[1].get("status") != "failed"
                or rows[1].get("invocationId") != "matrix-repetition-1"
                or any(row.get("providerCalls") != 1 or row.get("retryCount") != 0 for row in rows)
            ):
                raise ValueError("failed reduced matrix evidence is invalid")
            matrix_reservation_ids.update(
                str(row["budget"]["reservationId"]) for row in rows
            )
            models.append(
                {
                    "modelId": model_id,
                    "status": "FAILED_CLOSED_AFTER_SMOKE",
                    "rawArtifact": partial_path.relative_to(root).as_posix(),
                    "rawArtifactSha256": sha256_file(partial_path),
                    "providerCalls": 2,
                    "retryCount": 0,
                    "smokeReleaseAllowed": rows[0]["releaseAllowed"],
                    "failedInvocation": rows[1]["invocationId"],
                    "providerDiagnostic": rows[1]["providerDiagnostic"],
                    "conservativeDebitEur": sum(
                        float(row["budget"]["conservativeDebitEur"]) for row in rows
                    ),
                    "eligibleForFullConditionPilot": False,
                }
            )
        else:
            raise ValueError("reduced matrix artifact state is ambiguous")

    cross_model = []
    for left_id, right_id in combinations(successful_maps, 2):
        agreement = 0
        compared = 0
        score_differences = []
        for repetition in range(2):
            left = successful_maps[left_id][repetition]
            right = successful_maps[right_id][repetition]
            for case_id in left:
                compared += 1
                agreement += left[case_id]["governedAction"] == right[case_id]["governedAction"]
                score_differences.append(
                    abs(
                        left[case_id]["normalizedRiskScore"]
                        - right[case_id]["normalizedRiskScore"]
                    )
                )
        cross_model.append(
            {
                "leftModelId": left_id,
                "rightModelId": right_id,
                "comparedObservations": compared,
                "governedActionAgreementRate": agreement / compared,
                "meanAbsoluteScoreDifference": fmean(score_differences),
                "maximumAbsoluteScoreDifference": max(score_differences),
            }
        )
    ledger_path = root / config["budget"]["ledger"]
    ledger = read_jsonl(ledger_path)
    settlement_indexes = [
        index
        for index, row in enumerate(ledger)
        if row.get("recordType") == "budget_settlement"
        and row.get("reservationId") in matrix_reservation_ids
    ]
    if len(settlement_indexes) != len(matrix_reservation_ids):
        raise ValueError("reduced matrix budget settlements changed")
    reduced_ledger = ledger[: max(settlement_indexes) + 1]
    report = {
        "schemaVersion": "purposebound-finance.reduced-matrix-analysis.v2",
        "status": "COMPLETE_WITH_MODEL_FAILURE",
        "scope": "ELIGIBLE_MODELS_AFTER_COMPATIBILITY_EXCLUSIONS",
        "configuredModelCount": len(models),
        "passingModelCount": sum(model["status"] == "PASSED" for model in models),
        "failedModelCount": sum(model["status"] != "PASSED" for model in models),
        "models": models,
        "crossModelAgreement": cross_model,
        "excludedBeforeMatrix": config["eligibleReducedMatrix"]["excludedModelIds"],
        "budget": {
            "ledger": config["budget"]["ledger"],
            "ledgerPrefixRecordCount": len(reduced_ledger),
            "ledgerPrefixHash": sha256_json(reduced_ledger),
            "categoryCommittedEur": committed_category_eur(
                reduced_ledger,
                REDUCED_CATEGORY,
            ),
            "categoryAuthorizedEur": config["eligibleReducedMatrix"][
                "maximumMatrixBudgetEur"
            ],
            "globalCommittedEur": committed_budget_eur(reduced_ledger),
            "absoluteAuthorizedEur": config["budget"]["absoluteAuthorizedEur"],
        },
        "limitations": [
            "Claude and DeepSeek were excluded by earlier phase-two compatibility failures.",
            "Gemma passed one record but failed its first 40-record invocation and was not retried.",
            "Each passing model has two 40-record repetitions; this remains a reduced pilot.",
            "Model scores are not calibrated probabilities and cross-model comparisons are diagnostic.",
        ],
        "reportHash": "",
    }
    material = dict(report)
    material.pop("reportHash")
    report["reportHash"] = sha256_json(material)
    return report
