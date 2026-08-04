"""Reproduce the five-condition OpenRouter pilot report."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import fmean
from typing import Any

from purposebench.utils import read_jsonl, sha256_file, sha256_json
from purposebench.v2.condition_pilot import (
    CONDITIONS,
    FULL_CONDITION_CATEGORY,
    FULL_DATA_CONDITIONS,
    load_condition_context,
)
from purposebench.v2.frontier_matrix import committed_budget_eur
from purposebench.v2.inference_pilot import load_paired_records
from purposebench.v2.phase_budget import committed_category_eur


def _assessment_map(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    case_ids = row["orderedCaseIds"]
    assessments = row["governedActionBatch"]["assessments"]
    if len(case_ids) != 8 or len(assessments) != 8:
        raise ValueError("condition pilot assessment count changed")
    result = {}
    for assessment in assessments:
        index = assessment["index"]
        if not isinstance(index, int) or not 0 <= index < 8:
            raise ValueError("condition pilot assessment index is invalid")
        result[str(case_ids[index])] = assessment
    if len(result) != 8:
        raise ValueError("condition pilot case mapping is incomplete")
    return result


def _pair_metrics(
    assessments: dict[str, dict[str, Any]],
    pairs: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    action_influences = 0
    score_differences = 0
    score_gaps = []
    for case_a, case_b in pairs.values():
        left = assessments[case_a]
        right = assessments[case_b]
        action_influences += left["governedAction"] != right["governedAction"]
        score_differences += left["normalizedRiskScore"] != right["normalizedRiskScore"]
        score_gaps.append(abs(left["normalizedRiskScore"] - right["normalizedRiskScore"]))
    return {
        "pairs": len(pairs),
        "governedActionInfluencedPairs": action_influences,
        "governedActionInfluenceRate": action_influences / len(pairs),
        "scoreDifferentPairs": score_differences,
        "scoreDifferenceRate": score_differences / len(pairs),
        "meanAbsolutePairScoreDifference": fmean(score_gaps),
        "maximumAbsolutePairScoreDifference": max(score_gaps),
    }


def build_condition_pilot_report(root: Path) -> dict[str, Any]:
    config, manifest = load_condition_context(
        root,
        root / "configs/v2/openrouter-phase2.json",
    )
    raw_path = root / (
        "results/v2/raw/inference/"
        "openrouter-phase2-full-condition-pilot-moonshotai-kimi-k3.jsonl"
    )
    manifest_path = root / (
        "results/v2/manifests/"
        "openrouter-phase2-full-condition-pilot-moonshotai-kimi-k3.json"
    )
    rows = read_jsonl(raw_path)
    result_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        len(rows) != 5
        or [row.get("condition") for row in rows] != list(CONDITIONS)
        or result_manifest.get("status") != "COMPLETE_WITH_FAILURES"
        or result_manifest.get("rawArtifactSha256") != sha256_file(raw_path)
        or any(
            row.get("providerCalls") != 1
            or row.get("retryCount") != 0
            or row.get("modelManifestHash") != manifest["manifestHash"]
            or row.get("contractMaterial", {}).get("controlledExposureConsentHash")
            != config["fullConditionPilot"]["controlledExposureConsentHash"]
            for row in rows
        )
    ):
        raise ValueError("full condition pilot evidence is invalid")
    for row in rows:
        expected_transmission = row["condition"] in FULL_DATA_CONDITIONS
        if row.get("prohibitedSyntheticFieldsTransmitted") is not expected_transmission:
            raise ValueError("full condition pilot exposure evidence changed")
        if row["status"] == "passed" and row.get("releaseAllowed") is not True:
            raise ValueError("successful full condition output was not released")
    failures = [row for row in rows if row["status"] == "failed"]
    if (
        len(failures) != 1
        or failures[0]["condition"] != "prompt_only_purpose_restriction"
        or failures[0]["providerDiagnostic"]["category"] != "RATE_LIMIT"
    ):
        raise ValueError("full condition pilot failure inventory changed")

    dataset = load_paired_records(root / config["dataset"], pair_limit=4)
    pairs = {
        str(row["pair_id"]): (
            next(str(item["case_id"]) for item in dataset if item["pair_id"] == row["pair_id"] and item["variant"] == "A"),
            next(str(item["case_id"]) for item in dataset if item["pair_id"] == row["pair_id"] and item["variant"] == "B"),
        )
        for row in dataset
    }
    successful_maps = {
        row["condition"]: _assessment_map(row) for row in rows if row["status"] == "passed"
    }
    baseline = successful_maps["all_data_no_policy"]
    condition_results = []
    for row in rows:
        result: dict[str, Any] = {
            "condition": row["condition"],
            "status": row["status"].upper(),
            "prohibitedSyntheticFieldsTransmitted": row[
                "prohibitedSyntheticFieldsTransmitted"
            ],
            "identifiersPseudonymized": row["identifiersPseudonymized"],
            "releasePolicyMode": row["releasePolicyMode"],
            "providerCalls": 1,
            "retryCount": 0,
            "conservativeDebitEur": row["budget"]["conservativeDebitEur"],
        }
        if row["status"] == "failed":
            result["providerDiagnostic"] = row["providerDiagnostic"]
        else:
            assessments = successful_maps[row["condition"]]
            deltas = [
                abs(
                    assessments[case_id]["normalizedRiskScore"]
                    - baseline[case_id]["normalizedRiskScore"]
                )
                for case_id in baseline
            ]
            action_agreement = sum(
                assessments[case_id]["governedAction"]
                == baseline[case_id]["governedAction"]
                for case_id in baseline
            )
            recommendation_agreement = sum(
                assessments[case_id]["rawRecommendation"]
                == baseline[case_id]["rawRecommendation"]
                for case_id in baseline
            )
            result.update(
                {
                    "releaseAllowed": True,
                    "disclosureFindingCount": len(row["disclosureFindings"]),
                    "pairedPurpose": _pair_metrics(assessments, pairs),
                    "comparisonWithAllDataNoPolicy": {
                        "comparedRecords": 8,
                        "governedActionAgreementRate": action_agreement / 8,
                        "rawRecommendationAgreementRate": recommendation_agreement / 8,
                        "meanAbsoluteScoreDifference": fmean(deltas),
                        "maximumAbsoluteScoreDifference": max(deltas),
                    },
                }
            )
        condition_results.append(result)

    ledger_path = root / config["budget"]["ledger"]
    ledger = read_jsonl(ledger_path)
    final_reservation = rows[-1]["budget"]["reservationId"]
    final_settlements = [
        index
        for index, row in enumerate(ledger)
        if row.get("recordType") == "budget_settlement"
        and row.get("reservationId") == final_reservation
    ]
    if len(final_settlements) != 1:
        raise ValueError("full condition pilot final settlement changed")
    pilot_ledger = ledger[: final_settlements[0] + 1]
    report = {
        "schemaVersion": "purposebound-finance.full-condition-analysis.v2",
        "status": "COMPLETE_WITH_FAILURES",
        "modelId": manifest["modelId"],
        "modelManifestHash": manifest["manifestHash"],
        "controlledExposureConsent": config["fullConditionPilot"][
            "controlledExposureConsent"
        ],
        "controlledExposureConsentHash": config["fullConditionPilot"][
            "controlledExposureConsentHash"
        ],
        "rawArtifact": raw_path.relative_to(root).as_posix(),
        "rawArtifactSha256": sha256_file(raw_path),
        "conditionResults": condition_results,
        "passedConditionCount": len(successful_maps),
        "failedConditionCount": len(failures),
        "budget": {
            "ledger": config["budget"]["ledger"],
            "ledgerPrefixRecordCount": len(pilot_ledger),
            "ledgerPrefixHash": sha256_json(pilot_ledger),
            "categoryCommittedEur": committed_category_eur(
                pilot_ledger,
                FULL_CONDITION_CATEGORY,
            ),
            "categoryAuthorizedEur": config["fullConditionPilot"][
                "maximumPilotBudgetEur"
            ],
            "globalCommittedEur": committed_budget_eur(pilot_ledger),
            "absoluteAuthorizedEur": config["budget"]["absoluteAuthorizedEur"],
        },
        "limitations": [
            "The prompt-only condition was rate-limited and was not retried, so it has no outcome comparison.",
            "Each condition has one eight-record invocation; differences cannot be separated from sampling variability.",
            "The full-data conditions used public records plus synthetic internal fields, never real internal customer data.",
            "All identifiers were pseudonymized and every successful output passed a native Compex release policy.",
        ],
        "reportHash": "",
    }
    material = dict(report)
    material.pop("reportHash")
    report["reportHash"] = sha256_json(material)
    return report
