"""Deterministic comparison metrics for governed frontier pilot artifacts."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any

from purposebench.utils import read_jsonl, sha256_file, sha256_json
from purposebench.v2.frontier_matrix import (
    BUDGET_LEDGER,
    committed_budget_eur,
    load_frontier_matrix,
)
from purposebench.v2.inference_pilot import load_paired_records


def _rank(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average_rank = (index + 1 + end) / 2
        for original_index, _ in ordered[index:end]:
            ranks[original_index] = average_rank
        index = end
    return ranks


def _correlation(left: list[float], right: list[float]) -> float | None:
    left_mean = fmean(left)
    right_mean = fmean(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right, strict=True)
    )
    left_scale = math.sqrt(sum((value - left_mean) ** 2 for value in left))
    right_scale = math.sqrt(sum((value - right_mean) ** 2 for value in right))
    if left_scale == 0 or right_scale == 0:
        return None
    return numerator / (left_scale * right_scale)


def _passed_row(raw_path: Path) -> dict[str, Any]:
    passed = [row for row in read_jsonl(raw_path) if row.get("status") == "passed"]
    if len(passed) != 1:
        raise ValueError(f"frontier pilot must contain exactly one passing row: {raw_path}")
    return passed[0]


def build_frontier_comparison(
    benchmark_root: Path,
    config_path: Path,
) -> dict[str, Any]:
    config, models = load_frontier_matrix(benchmark_root, config_path.resolve())
    dataset_path = (benchmark_root / config["dataset"]).resolve()
    dataset_rows = load_paired_records(dataset_path, pair_limit=20)
    if len(dataset_rows) != 40:
        raise ValueError("frontier comparison requires exactly 40 ordered records")
    pair_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(dataset_rows):
        pair_indices[str(row["pair_id"])].append(index)
    if len(pair_indices) != 20 or any(len(indices) != 2 for indices in pair_indices.values()):
        raise ValueError("frontier comparison requires 20 complete pairs")

    model_results: list[dict[str, Any]] = []
    passed_outputs: dict[str, dict[str, Any]] = {}
    source_artifacts: list[dict[str, str]] = []
    finished_at: list[str] = []
    transmitted_hashes: set[str] = set()
    pilot_debit = 0.0
    for model in models:
        slug = model["artifactSlug"]
        raw_relative = Path(
            f"results/v2/raw/inference/openrouter-frontier-pilot-{slug}.jsonl"
        )
        manifest_relative = Path(
            f"results/v2/manifests/openrouter-frontier-pilot-{slug}.json"
        )
        raw_path = benchmark_root / raw_relative
        manifest_path = benchmark_root / manifest_relative
        if not raw_path.exists() or not manifest_path.exists():
            smoke_partial = (
                benchmark_root
                / f"results/v2/raw/inference/openrouter-frontier-smoke-{slug}.jsonl.partial"
            )
            failed_attempts = (
                sum(
                    row.get("status") == "failed"
                    for row in read_jsonl(smoke_partial)
                )
                if smoke_partial.exists()
                else 0
            )
            model_results.append(
                {
                    "modelId": model["modelId"],
                    "status": "INELIGIBLE_SMOKE_GATE",
                    "failedSmokeAttempts": failed_attempts,
                    "pilotNetworkCalls": 0,
                }
            )
            continue

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("status") != "passed"
            or manifest.get("model") != model["modelId"]
            or manifest.get("frontierMatrix", {}).get("phase") != "pilot"
            or manifest.get("modelManifestHash") != model["manifestHash"]
            or manifest.get("rawArtifact") != raw_relative.as_posix()
            or manifest.get("rawArtifactSha256") != sha256_file(raw_path)
        ):
            raise ValueError(f"frontier pilot manifest integrity failed: {model['modelId']}")
        row = _passed_row(raw_path)
        if (
            row.get("recordCount") != 40
            or row.get("completePairCount") != 20
            or row.get("releaseAllowed") is not True
            or row.get("modelManifestHash") != model["manifestHash"]
            or row.get("pinnedModelId") != model["modelId"]
        ):
            raise ValueError(f"frontier pilot evidence is invalid: {model['modelId']}")
        output = row["quarantinedOutput"]
        decisions = list(output.get("decisions", []))
        risk_scores = [float(value) for value in output.get("risk_scores", [])]
        if len(decisions) != 40 or len(risk_scores) != 40:
            raise ValueError(f"frontier pilot output cardinality failed: {model['modelId']}")
        pair_decision_agreements = 0
        pair_risk_agreements = 0
        pair_risk_deltas: list[float] = []
        for indices in pair_indices.values():
            left_index, right_index = indices
            pair_decision_agreements += (
                decisions[left_index] == decisions[right_index]
            )
            delta = abs(risk_scores[left_index] - risk_scores[right_index])
            pair_risk_deltas.append(delta)
            pair_risk_agreements += delta == 0
        counts = Counter(decisions)
        tokens = row["modelEvidence"]["tokenUse"]
        provider_reported = row["modelEvidence"].get("providerReportedCost")
        debit = float(row["budgetDebitEur"])
        pilot_debit += debit
        transmitted_hashes.add(str(row["transmittedRecordHash"]))
        finished_at.append(str(row["finishedAt"]))
        passed_outputs[model["modelId"]] = {
            "decisions": decisions,
            "riskScores": risk_scores,
        }
        model_results.append(
            {
                "modelId": model["modelId"],
                "canonicalSlug": model["canonicalSlug"],
                "providerRoute": model["providerRouting"]["only"],
                "status": "PASSED",
                "records": 40,
                "pairs": 20,
                "decisionCounts": dict(sorted(counts.items())),
                "manualReviewRate": counts.get("MANUAL_REVIEW", 0) / 40,
                "standardReviewRate": counts.get("STANDARD_REVIEW", 0) / 40,
                "riskScore": {
                    "minimum": min(risk_scores),
                    "mean": fmean(risk_scores),
                    "maximum": max(risk_scores),
                    "populationStdDev": pstdev(risk_scores),
                },
                "paired": {
                    "decisionAgreementRate": pair_decision_agreements / 20,
                    "riskScoreExactAgreementRate": pair_risk_agreements / 20,
                    "meanAbsoluteRiskScoreDelta": fmean(pair_risk_deltas),
                },
                "durationSeconds": row["durationSeconds"],
                "tokenUse": tokens,
                "conservativeDebitEur": debit,
                "providerReportedCost": provider_reported,
            }
        )
        source_artifacts.extend(
            [
                {"path": raw_relative.as_posix(), "sha256": sha256_file(raw_path)},
                {
                    "path": manifest_relative.as_posix(),
                    "sha256": sha256_file(manifest_path),
                },
            ]
        )

    if len(transmitted_hashes) != 1:
        raise ValueError("frontier pilots did not use one identical transmitted projection")
    pairwise: list[dict[str, Any]] = []
    for left_id, right_id in combinations(sorted(passed_outputs), 2):
        left = passed_outputs[left_id]
        right = passed_outputs[right_id]
        agreement = sum(
            left_value == right_value
            for left_value, right_value in zip(
                left["decisions"], right["decisions"], strict=True
            )
        )
        pairwise.append(
            {
                "leftModelId": left_id,
                "rightModelId": right_id,
                "decisionAgreementRate": agreement / 40,
                "riskScoreSpearmanCorrelation": _correlation(
                    _rank(left["riskScores"]),
                    _rank(right["riskScores"]),
                ),
            }
        )

    passing_ids = sorted(passed_outputs)
    unanimous = 0
    majority_counts: Counter[str] = Counter()
    for index in range(40):
        decisions = [passed_outputs[model_id]["decisions"][index] for model_id in passing_ids]
        counts = Counter(decisions)
        unanimous += len(counts) == 1
        majority_counts[counts.most_common(1)[0][0]] += 1

    ledger_rows = read_jsonl(benchmark_root / BUDGET_LEDGER)
    known_provider_cost = sum(
        float(row["providerReportedCost"]["amount"])
        for row in ledger_rows
        if isinstance(row.get("providerReportedCost"), dict)
        and row["providerReportedCost"].get("unit") == "OPENROUTER_CREDITS"
    )
    committed = committed_budget_eur(ledger_rows)
    return {
        "schemaVersion": "purposebound-finance.frontier-comparison.v2",
        "derivedAt": max(finished_at),
        "matrixHash": config["modelMatrixHash"],
        "dataset": config["dataset"],
        "datasetSha256": sha256_file(dataset_path),
        "transmittedRecordHash": next(iter(transmitted_hashes)),
        "eligibleModelCount": len(passing_ids),
        "configuredModelCount": len(models),
        "recordsPerModel": 40,
        "pairsPerModel": 20,
        "models": model_results,
        "crossModel": {
            "passingModelIds": passing_ids,
            "unanimousDecisionRecords": unanimous,
            "unanimousDecisionRate": unanimous / 40,
            "majorityDecisionCounts": dict(sorted(majority_counts.items())),
            "pairwise": pairwise,
        },
        "budget": {
            "authorizedEur": config["totalAuthorizedCostEur"],
            "committedEur": committed,
            "remainingEur": round(config["totalAuthorizedCostEur"] - committed, 9),
            "pilotConservativeDebitEur": round(pilot_debit, 9),
            "knownProviderReportedCostOpenRouterCredits": round(
                known_provider_cost, 9
            ),
            "failedCallsWithoutCostEvidenceRemainFullyDebited": True,
        },
        "sourceArtifacts": source_artifacts,
        "limitations": [
            "This is a 40-record diagnostic pilot, not a population estimate.",
            "Risk-score scales are model-specific; rank correlations do not make them calibrated.",
            "Paired agreement tests the selected transformations only and is not a general fairness guarantee.",
            "Claude is absent from cross-model metrics because no Claude smoke gate passed.",
            "Remote processing occurred through OpenRouter under pinned ZDR routes.",
        ],
        "comparisonHash": "",
    }


def finalize_frontier_comparison(value: dict[str, Any]) -> dict[str, Any]:
    material = dict(value)
    material.pop("comparisonHash", None)
    value["comparisonHash"] = sha256_json(material)
    return value
