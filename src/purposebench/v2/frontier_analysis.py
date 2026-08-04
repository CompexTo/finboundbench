"""Deterministic validation and summaries for the governed frontier pilot."""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
from typing import Any

from purposebench.utils import read_jsonl, sha256_file, sha256_json
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

SUMMARY_FIELDS = (
    "modelId",
    "canonicalSlug",
    "providerRoute",
    "status",
    "recordCount",
    "pairCount",
    "decisionAgreementRate",
    "riskScoreAgreementRate",
    "pairedInfluenceRate",
    "meanAbsoluteRiskScoreDifference",
    "maximumAbsoluteRiskScoreDifference",
    "disclosureCount",
    "releaseAllowed",
    "evidenceCompleteness",
    "durationSeconds",
    "inputTokens",
    "outputTokens",
    "totalTokens",
    "conservativeCostEur",
    "providerReportedCostOpenRouterCredits",
    "modelManifestHash",
    "matrixHash",
    "rawArtifact",
    "rawArtifactSha256",
)

REQUIRED_MODEL_EVIDENCE = {
    "attemptCount",
    "contractHash",
    "cost",
    "destinationHost",
    "destinationPort",
    "destinationProvider",
    "httpMethod",
    "latencyMs",
    "modelId",
    "modelVersion",
    "payloadHash",
    "processingClassification",
    "providerReportedCost",
    "pseudonymized",
    "recordedAt",
    "requestBytes",
    "responseBytes",
    "responseHash",
    "secretReferenceMetadata",
    "tokenUse",
    "transmittedFields",
}


def _resolved_artifact(benchmark_root: Path, relative: str, expected_root: Path) -> Path:
    path = (benchmark_root / relative).resolve()
    if expected_root.resolve() not in path.parents or not path.is_file():
        raise ValueError("frontier analysis artifact is missing or outside its directory")
    return path


def _validate_budget_prefix(
    benchmark_root: Path,
    budget: dict[str, Any],
    *,
    model_id: str,
) -> None:
    if budget.get("ledgerArtifact") != str(BUDGET_LEDGER).replace("\\", "/"):
        raise ValueError("frontier pilot budget ledger substitution detected")
    ledger = read_jsonl(benchmark_root / BUDGET_LEDGER)
    count = budget.get("ledgerPrefixRecordCount")
    if (
        not isinstance(count, int)
        or count < 1
        or count > len(ledger)
        or sha256_json(ledger[:count]) != budget.get("ledgerPrefixHash")
    ):
        raise ValueError("frontier pilot budget prefix integrity failed")
    reservation_id = budget.get("reservationId")
    settlements = [
        row
        for row in ledger[:count]
        if row.get("recordType") == "budget_settlement"
        and row.get("reservationId") == reservation_id
    ]
    if (
        len(settlements) != 1
        or settlements[0].get("modelId") != model_id
        or settlements[0].get("phase") != "pilot"
        or settlements[0].get("outcome") != "passed"
        or float(settlements[0].get("budgetDebitEur", -1))
        != float(budget.get("budgetDebitEur", -2))
    ):
        raise ValueError("frontier pilot budget settlement is invalid")


def _passed_summary(
    benchmark_root: Path,
    config: dict[str, Any],
    model: dict[str, Any],
    manifest_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frontier = manifest.get("frontierMatrix")
    if (
        manifest.get("schemaVersion")
        != "purposebound-finance.remote-pilot-manifest.v2"
        or manifest.get("status") != "passed"
        or manifest.get("model") != model["modelId"]
        or manifest.get("modelManifestHash") != model["manifestHash"]
        or not isinstance(frontier, dict)
        or frontier.get("phase") != "pilot"
        or frontier.get("matrixHash") != config["modelMatrixHash"]
    ):
        raise ValueError("frontier pilot manifest identity is invalid")
    raw_path = _resolved_artifact(
        benchmark_root,
        str(manifest.get("rawArtifact", "")),
        benchmark_root / "results/v2/raw/inference",
    )
    if sha256_file(raw_path) != manifest.get("rawArtifactSha256"):
        raise ValueError("frontier pilot raw artifact integrity failed")
    attempts = read_jsonl(raw_path)
    passed = [row for row in attempts if row.get("status") == "passed"]
    if len(passed) != 1 or len(attempts) != manifest.get("attemptCount"):
        raise ValueError("frontier pilot attempt cardinality is invalid")
    row = passed[0]
    if (
        row.get("recordCount") != 40
        or row.get("completePairCount") != 20
        or row.get("releaseAllowed") is not True
        or row.get("pinnedModelId") != model["modelId"]
        or row.get("modelManifestHash") != model["manifestHash"]
        or row.get("modelProvider") != "OPENROUTER"
        or row.get("disclosureFindings") != []
    ):
        raise ValueError("frontier pilot did not pass required release controls")
    dataset_path = _resolved_artifact(
        benchmark_root,
        str(row["datasetPath"]),
        benchmark_root / "data/v2/generated",
    )
    if sha256_file(dataset_path) != row.get("datasetSha256"):
        raise ValueError("frontier pilot dataset integrity failed")
    dataset_rows = load_paired_records(dataset_path, pair_limit=20)
    case_ids = [str(item["case_id"]) for item in dataset_rows]
    quarantined = row["quarantinedOutput"]
    parsed_output = json.loads(quarantined) if isinstance(quarantined, str) else quarantined
    normalized = _validate_response(parsed_output, case_ids)
    if sha256_json(normalized) != row.get("normalizedResultsHash"):
        raise ValueError("frontier pilot normalized result integrity failed")
    pair_metrics = _pair_agreement(normalized, dataset_rows)
    evidence = row.get("modelEvidence")
    if not isinstance(evidence, dict):
        raise TypeError("frontier pilot model evidence is missing")
    completeness = len(REQUIRED_MODEL_EVIDENCE.intersection(evidence)) / len(
        REQUIRED_MODEL_EVIDENCE
    )
    if completeness != 1.0:
        raise ValueError("frontier pilot model evidence is incomplete")
    _validate_budget_prefix(benchmark_root, manifest["budget"], model_id=model["modelId"])
    token_use = evidence["tokenUse"]
    reported = evidence.get("providerReportedCost") or {}
    return {
        "modelId": model["modelId"],
        "canonicalSlug": model["canonicalSlug"],
        "providerRoute": model["providerRouting"]["only"][0],
        "status": "passed",
        "recordCount": row["recordCount"],
        "pairCount": pair_metrics["pairs"],
        "decisionAgreementRate": pair_metrics["decisionAgreementRate"],
        "riskScoreAgreementRate": pair_metrics["riskScoreAgreementRate"],
        "pairedInfluenceRate": pair_metrics["pairedInfluenceRate"],
        "meanAbsoluteRiskScoreDifference": pair_metrics[
            "meanAbsoluteRiskScoreDifference"
        ],
        "maximumAbsoluteRiskScoreDifference": pair_metrics[
            "maximumAbsoluteRiskScoreDifference"
        ],
        "disclosureCount": len(row["disclosureFindings"]),
        "releaseAllowed": row["releaseAllowed"],
        "evidenceCompleteness": completeness,
        "durationSeconds": row["durationSeconds"],
        "inputTokens": token_use["inputTokens"],
        "outputTokens": token_use["outputTokens"],
        "totalTokens": token_use["totalTokens"],
        "conservativeCostEur": row["budgetDebitEur"],
        "providerReportedCostOpenRouterCredits": reported.get("amount"),
        "modelManifestHash": model["manifestHash"],
        "matrixHash": config["modelMatrixHash"],
        "rawArtifact": str(raw_path.relative_to(benchmark_root)).replace("\\", "/"),
        "rawArtifactSha256": sha256_file(raw_path),
    }


def analyze_frontier_pilots(
    benchmark_root: Path,
    config_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    config, models = load_frontier_matrix(benchmark_root, config_path)
    summaries: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    compatibility_artifacts: list[dict[str, str]] = []
    pilot_ledger_prefix_counts: list[int] = []
    for model in models:
        slug = model["artifactSlug"]
        manifest_path = (
            benchmark_root
            / "results/v2/manifests"
            / f"openrouter-frontier-pilot-{slug}.json"
        )
        if manifest_path.exists():
            summaries.append(_passed_summary(benchmark_root, config, model, manifest_path))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            pilot_ledger_prefix_counts.append(manifest["budget"]["ledgerPrefixRecordCount"])
            continue
        partial_path = (
            benchmark_root
            / "results/v2/raw/inference"
            / f"openrouter-frontier-smoke-{slug}.jsonl.partial"
        )
        failures = [row for row in read_jsonl(partial_path) if row.get("status") == "failed"]
        family_paths = sorted(
            (benchmark_root / "results/v2/raw/inference").glob(
                "openrouter-frontier-smoke-anthropic-claude-*.jsonl.partial"
            )
        )
        family_failures = sum(
            row.get("status") == "failed"
            for path in family_paths
            for row in read_jsonl(path)
        )
        compatibility_artifacts.extend(
            {
                "path": str(path.relative_to(benchmark_root)).replace("\\", "/"),
                "sha256": sha256_file(path),
            }
            for path in family_paths
        )
        exclusions.append(
            {
                "modelId": model["modelId"],
                "canonicalSlug": model["canonicalSlug"],
                "providerRoute": model["providerRouting"]["only"][0],
                "status": "ineligible_smoke_gate_failed",
                "selectedModelFailedSmokeAttempts": len(failures),
                "claudeFamilyFailedSmokeAttempts": family_failures,
                "lastError": failures[-1].get("error") if failures else "missing smoke evidence",
                "pilotReservationCreated": False,
                "modelManifestHash": model["manifestHash"],
                "matrixHash": config["modelMatrixHash"],
                "rawArtifact": (
                    str(partial_path.relative_to(benchmark_root)).replace("\\", "/")
                    if partial_path.exists()
                    else None
                ),
                "rawArtifactSha256": sha256_file(partial_path) if partial_path.exists() else None,
            }
        )
    ledger_path = benchmark_root / BUDGET_LEDGER
    ledger = read_jsonl(ledger_path)
    pilot_prefix_count = max(pilot_ledger_prefix_counts)
    pilot_ledger = ledger[:pilot_prefix_count]
    analysis_manifest = {
        "schemaVersion": "purposebound-finance.frontier-analysis.v2",
        "matrixHash": config["modelMatrixHash"],
        "modelManifest": config["modelManifestPath"],
        "passedPilotModels": len(summaries),
        "excludedPilotModels": len(exclusions),
        "totalAuthorizedCostEur": config["totalAuthorizedCostEur"],
        "committedCostEur": committed_budget_eur(pilot_ledger),
        "budgetLedger": str(BUDGET_LEDGER).replace("\\", "/"),
        "budgetLedgerPrefixRecordCount": pilot_prefix_count,
        "budgetLedgerPrefixHash": sha256_json(pilot_ledger),
        "sourceRawArtifacts": [
            {"path": row["rawArtifact"], "sha256": row["rawArtifactSha256"]}
            for row in summaries
            if row["rawArtifact"] is not None
        ]
        + compatibility_artifacts,
        "limitations": [
            "This is a governed remote-processing pilot, not a population estimate.",
            "Paired influence covers decision or numeric risk-score changes.",
            "Claude is excluded because no strict ZDR smoke gate passed.",
            "Provider costs use OpenRouter credits; budget debits use USD/EUR parity.",
        ],
    }
    return summaries, exclusions, analysis_manifest


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _csv_text(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def write_frontier_analysis(
    benchmark_root: Path,
    summaries: list[dict[str, Any]],
    exclusions: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Path]:
    derived = benchmark_root / "results/v2/derived"
    summary_path = derived / "openrouter-frontier-pilot-summary.csv"
    exclusions_path = derived / "openrouter-frontier-pilot-exclusions.csv"
    _atomic_text(summary_path, _csv_text(summaries, SUMMARY_FIELDS))
    exclusion_fields = tuple(exclusions[0]) if exclusions else ("modelId", "status")
    _atomic_text(exclusions_path, _csv_text(exclusions, exclusion_fields))
    complete_manifest = {
        **manifest,
        "summaryArtifact": str(summary_path.relative_to(benchmark_root)).replace("\\", "/"),
        "summaryArtifactSha256": sha256_file(summary_path),
        "exclusionsArtifact": str(exclusions_path.relative_to(benchmark_root)).replace(
            "\\", "/"
        ),
        "exclusionsArtifactSha256": sha256_file(exclusions_path),
    }
    manifest_path = benchmark_root / "results/v2/manifests/openrouter-frontier-analysis.json"
    _atomic_text(manifest_path, json.dumps(complete_manifest, indent=2, sort_keys=True) + "\n")
    report_path = benchmark_root / "docs/v2/FRONTIER_PILOT_RESULTS.md"
    lines = [
        "# Governed frontier pilot results",
        "",
        "These deterministic summaries are regenerated from hash-validated raw JSONL.",
        "The remote projection was processed by OpenRouter and did not remain local.",
        "",
        "| Model | Route | Paired influence | Decision agreement | Risk-score agreement | Seconds | Conservative EUR |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summaries:
        lines.append(
            f"| `{row['modelId']}` | `{row['providerRoute']}` | "
            f"{row['pairedInfluenceRate']:.3f} | {row['decisionAgreementRate']:.3f} | "
            f"{row['riskScoreAgreementRate']:.3f} | {row['durationSeconds']:.3f} | "
            f"{row['conservativeCostEur']:.8f} |"
        )
    lines.extend(("", "## Exclusions", ""))
    for row in exclusions:
        lines.append(
            f"- `{row['modelId']}`: no forty-record run; its strict smoke gate failed "
            f"after {row['selectedModelFailedSmokeAttempts']} retained attempt(s). "
            f"The Claude family accumulated {row['claudeFamilyFailedSmokeAttempts']} "
            "retained failed attempts across three model IDs."
        )
    lines.extend(("", "## Interpretation boundary", ""))
    lines.extend(f"- {item}" for item in complete_manifest["limitations"])
    _atomic_text(report_path, "\n".join(lines) + "\n")
    return {
        "summary": summary_path,
        "exclusions": exclusions_path,
        "manifest": manifest_path,
        "report": report_path,
    }
