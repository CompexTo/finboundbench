"""Reproduce position and batch-size diagnostics from governed raw evidence."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from purposebench.utils import read_jsonl, sha256_file, sha256_json
from purposebench.v2.frontier_matrix import committed_budget_eur
from purposebench.v2.phase_budget import committed_category_eur
from purposebench.v2.position_diagnostic import POSITION_CATEGORY


def _observations(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        case_ids = row["orderedCaseIds"]
        assessments = row["governedActionBatch"]["assessments"]
        if len(case_ids) != len(assessments):
            raise ValueError("position diagnostic mapping length changed")
        for assessment in assessments:
            index = assessment["index"]
            if not isinstance(index, int) or not 0 <= index < len(case_ids):
                raise ValueError("position diagnostic model index is invalid")
            observations[str(case_ids[index])].append(
                {
                    "invocationId": row["invocationId"],
                    "layout": row["layout"],
                    "layoutBatch": row["layoutBatch"],
                    "score": assessment["normalizedRiskScore"],
                    "recommendation": assessment["rawRecommendation"],
                    "governedAction": assessment["governedAction"],
                    "recommendationPolicyDisagreement": assessment[
                        "recommendationPolicyDisagreement"
                    ],
                }
            )
    return dict(observations)


def _layout_metrics(
    rows: list[dict[str, Any]],
    observations: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    original = next(row for row in rows if row["layout"] == "original_order")
    baseline = {
        case_id: assessment
        for case_id, assessment in zip(
            original["orderedCaseIds"],
            original["governedActionBatch"]["assessments"],
            strict=True,
        )
    }
    metrics = []
    for layout in sorted({str(row["layout"]) for row in rows}):
        comparable = [
            (case_id, observation)
            for case_id, values in observations.items()
            for observation in values
            if observation["layout"] == layout and case_id in baseline
        ]
        deltas = []
        governed_agreement = 0
        recommendation_agreement = 0
        for case_id, observation in comparable:
            reference = baseline[case_id]
            deltas.append(abs(observation["score"] - reference["normalizedRiskScore"]))
            governed_agreement += (
                observation["governedAction"] == reference["governedAction"]
            )
            recommendation_agreement += (
                observation["recommendation"] == reference["rawRecommendation"]
            )
        metrics.append(
            {
                "layout": layout,
                "comparableObservations": len(deltas),
                "meanAbsoluteScoreDeltaFromOriginal": fmean(deltas),
                "maximumAbsoluteScoreDeltaFromOriginal": max(deltas),
                "governedActionAgreementWithOriginal": governed_agreement / len(deltas),
                "rawRecommendationAgreementWithOriginal": (
                    recommendation_agreement / len(deltas)
                ),
            }
        )
    return metrics


def build_position_report(root: Path) -> dict[str, Any]:
    gpt_raw = root / (
        "results/v2/raw/inference/"
        "openrouter-phase2-position-openai-gpt-5-6-luna.jsonl"
    )
    gpt_manifest_path = root / (
        "results/v2/manifests/"
        "openrouter-phase2-position-openai-gpt-5-6-luna.json"
    )
    deepseek_raw = root / (
        "results/v2/raw/inference/"
        "openrouter-phase2-position-deepseek-deepseek-v4-pro.jsonl.partial"
    )
    gpt_manifest = json.loads(gpt_manifest_path.read_text(encoding="utf-8"))
    gpt_rows = read_jsonl(gpt_raw)
    if (
        gpt_manifest.get("status") != "PASSED"
        or gpt_manifest.get("rawArtifactSha256") != sha256_file(gpt_raw)
        or len(gpt_rows) != 11
        or any(
            row.get("status") != "passed"
            or row.get("releaseAllowed") is not True
            or row.get("providerCalls") != 1
            or row.get("retryCount") != 0
            or row.get("prohibitedSyntheticFieldsTransmitted") is not False
            for row in gpt_rows
        )
    ):
        raise ValueError("GPT position diagnostic evidence is invalid")
    deepseek_rows = read_jsonl(deepseek_raw)
    if (
        len(deepseek_rows) != 1
        or deepseek_rows[0].get("status") != "failed"
        or deepseek_rows[0].get("providerCalls") != 1
        or deepseek_rows[0].get("retryCount") != 0
    ):
        raise ValueError("DeepSeek position diagnostic failure evidence is invalid")
    observations = _observations(gpt_rows)
    repeated_observations = {
        case_id: values for case_id, values in observations.items() if len(values) > 1
    }
    score_ranges = [
        max(item["score"] for item in values) - min(item["score"] for item in values)
        for values in repeated_observations.values()
    ]
    governed_stable = sum(
        len({item["governedAction"] for item in values}) == 1
        for values in repeated_observations.values()
    )
    recommendation_stable = sum(
        len({item["recommendation"] for item in values}) == 1
        for values in repeated_observations.values()
    )
    disagreement_observations = [
        item["recommendationPolicyDisagreement"]
        for values in observations.values()
        for item in values
        if item["recommendationPolicyDisagreement"] is not None
    ]
    ledger_path = root / "results/v2/raw/inference/openrouter-frontier-budget.jsonl"
    ledger = read_jsonl(ledger_path)
    position_settlements = [
        index
        for index, row in enumerate(ledger)
        if row.get("recordType") == "budget_settlement"
        and row.get("reservationId") == deepseek_rows[0]["budget"]["reservationId"]
    ]
    if len(position_settlements) != 1:
        raise ValueError("position diagnostic budget settlement changed")
    position_ledger = ledger[: position_settlements[0] + 1]
    report = {
        "schemaVersion": "purposebound-finance.position-analysis.v2",
        "status": "COMPLETE_WITH_MODEL_FAILURE",
        "scope": "ELIGIBLE_MODELS_AFTER_CLAUDE_CLOSURE",
        "claudeGate3": False,
        "models": [
            {
                "modelId": "openai/gpt-5.6-luna",
                "status": "PASSED",
                "rawArtifact": gpt_raw.relative_to(root).as_posix(),
                "rawArtifactSha256": sha256_file(gpt_raw),
                "invocationCount": len(gpt_rows),
                "providerCalls": len(gpt_rows),
                "layouts": _layout_metrics(gpt_rows, observations),
                "caseStability": {
                    "observedCases": len(observations),
                    "repeatedlyObservedCases": len(repeated_observations),
                    "governedActionStableCases": governed_stable,
                    "governedActionStabilityRate": (
                        governed_stable / len(repeated_observations)
                    ),
                    "rawRecommendationStableCases": recommendation_stable,
                    "rawRecommendationStabilityRate": (
                        recommendation_stable / len(repeated_observations)
                    ),
                    "meanScoreRange": fmean(score_ranges),
                    "maximumScoreRange": max(score_ranges),
                },
                "recommendationPolicyDisagreement": {
                    "eligibleObservations": len(disagreement_observations),
                    "disagreementCount": sum(disagreement_observations),
                    "disagreementRate": (
                        sum(disagreement_observations) / len(disagreement_observations)
                        if disagreement_observations
                        else None
                    ),
                },
                "eligibleForReducedGovernedMatrix": True,
            },
            {
                "modelId": "deepseek/deepseek-v4-pro",
                "status": "FAILED_CLOSED",
                "rawArtifact": deepseek_raw.relative_to(root).as_posix(),
                "rawArtifactSha256": sha256_file(deepseek_raw),
                "providerCalls": 1,
                "failedInvocation": deepseek_rows[0]["invocationId"],
                "providerDiagnostic": deepseek_rows[0]["providerDiagnostic"],
                "eligibleForReducedGovernedMatrix": False,
                "priorFrontierReplicationsRemainInScope": True,
            },
        ],
        "budget": {
            "ledger": ledger_path.relative_to(root).as_posix(),
            "ledgerPrefixRecordCount": len(position_ledger),
            "ledgerPrefixHash": sha256_json(position_ledger),
            "categoryCommittedEur": committed_category_eur(
                position_ledger,
                POSITION_CATEGORY,
            ),
            "globalCommittedEur": committed_budget_eur(position_ledger),
        },
        "limitations": [
            "This is an eligible-model continuation after Claude closure, not Claude Gate 3.",
            "The diagnostic uses four focal pairs; only the full-batch layout includes all 40 records.",
            "DeepSeek stopped after its first failed invocation and was not retried.",
            "The results diagnose position and batch sensitivity and are not population estimates.",
        ],
        "reportHash": "",
    }
    material = dict(report)
    material.pop("reportHash")
    report["reportHash"] = sha256_json(material)
    return report
