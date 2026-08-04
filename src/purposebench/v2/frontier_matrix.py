"""Cumulative-budget orchestration for the governed OpenRouter frontier matrix."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import append_jsonl, read_jsonl, sha256_file, sha256_json
from purposebench.v2.remote_pilot import validate_remote_model_manifest

BUDGET_LEDGER = Path("results/v2/raw/inference/openrouter-frontier-budget.jsonl")


def validate_frontier_smoke_gate(
    benchmark_root: Path,
    smoke_manifest_path: Path,
    model: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a one-record gate and its ledger prefix before a paid pilot."""
    manifest_root = (benchmark_root / "results/v2/manifests").resolve()
    resolved_manifest = smoke_manifest_path.resolve()
    if manifest_root not in resolved_manifest.parents or not resolved_manifest.is_file():
        raise ValueError("frontier smoke manifest is outside the manifest directory")
    manifest = json.loads(resolved_manifest.read_text(encoding="utf-8"))
    if (
        manifest.get("schemaVersion")
        != "purposebound-finance.remote-pilot-manifest.v2"
        or manifest.get("status") != "passed"
        or manifest.get("model") != model["modelId"]
        or manifest.get("frontierMatrix", {}).get("phase") != "smoke"
    ):
        raise ValueError("frontier smoke manifest identity is invalid")

    raw_root = (benchmark_root / "results/v2/raw/inference").resolve()
    raw_path = (benchmark_root / str(manifest.get("rawArtifact", ""))).resolve()
    if (
        raw_root not in raw_path.parents
        or not raw_path.is_file()
        or sha256_file(raw_path) != manifest.get("rawArtifactSha256")
    ):
        raise ValueError("frontier smoke raw artifact integrity failed")
    passed = [row for row in read_jsonl(raw_path) if row.get("status") == "passed"]
    if not passed:
        raise ValueError("frontier smoke raw artifact has no passing attempt")
    successful = passed[-1]
    if (
        successful.get("recordCount") != 1
        or successful.get("releaseAllowed") is not True
        or successful.get("modelManifestHash") != model["manifestHash"]
        or successful.get("pinnedModelId") != model["modelId"]
        or successful.get("modelProvider") != "OPENROUTER"
    ):
        raise ValueError("frontier smoke did not pass for the current model manifest")

    budget = manifest.get("budget")
    if not isinstance(budget, dict):
        raise TypeError("frontier smoke budget evidence is missing")
    if budget.get("ledgerArtifact") != str(BUDGET_LEDGER).replace("\\", "/"):
        raise ValueError("frontier smoke budget ledger substitution detected")
    ledger_rows = read_jsonl(benchmark_root / BUDGET_LEDGER)
    prefix_count = budget.get("ledgerPrefixRecordCount")
    if (
        not isinstance(prefix_count, int)
        or prefix_count < 1
        or prefix_count > len(ledger_rows)
        or sha256_json(ledger_rows[:prefix_count]) != budget.get("ledgerPrefixHash")
    ):
        raise ValueError("frontier smoke budget ledger prefix integrity failed")
    reservation_id = budget.get("reservationId")
    settlements = [
        row
        for row in ledger_rows[:prefix_count]
        if row.get("recordType") == "budget_settlement"
        and row.get("reservationId") == reservation_id
    ]
    if (
        len(settlements) != 1
        or settlements[0].get("modelId") != model["modelId"]
        or settlements[0].get("phase") != "smoke"
        or settlements[0].get("outcome") != "passed"
        or float(settlements[0].get("budgetDebitEur", -1))
        != float(budget.get("budgetDebitEur", -2))
    ):
        raise ValueError("frontier smoke budget settlement is invalid")
    return successful


def load_frontier_matrix(
    benchmark_root: Path,
    config_path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    total = float(config["totalAuthorizedCostEur"])
    per_invocation = float(config["perInvocationAuthorizedCostEur"])
    if total != 10.0 or not 0 < per_invocation <= total:
        raise ValueError("frontier matrix must enforce the declared EUR 10 total budget")
    manifest_path = (benchmark_root / config["modelManifest"]).resolve()
    manifest_root = (benchmark_root / "docs/v2/model-manifests").resolve()
    if manifest_root not in manifest_path.parents:
        raise ValueError("frontier model manifest escaped the research manifest directory")
    matrix = json.loads(manifest_path.read_text(encoding="utf-8"))
    matrix_material = dict(matrix)
    matrix_hash = matrix_material.pop("matrixHash", None)
    if matrix_hash != sha256_json(matrix_material):
        raise ValueError("frontier model matrix hash mismatch")
    models = [validate_remote_model_manifest(model) for model in matrix["models"]]
    if [model["modelId"] for model in models] != config["modelIds"]:
        raise ValueError("frontier config and model manifest order differ")
    config["modelMatrixHash"] = matrix_hash
    config["modelManifestPath"] = str(manifest_path.relative_to(benchmark_root)).replace(
        "\\", "/"
    )
    return config, models


def committed_budget_eur(rows: Sequence[Mapping[str, Any]]) -> float:
    reservations: dict[str, dict[str, Any]] = {}
    settled: set[str] = set()
    for row in rows:
        reservation_id = str(row["reservationId"])
        if row["recordType"] == "budget_reservation":
            if reservation_id in reservations:
                raise ValueError("duplicate budget reservation")
            authorized = float(row["authorizedCostEur"])
            if authorized <= 0:
                raise ValueError("budget reservation must be positive")
            reservations[reservation_id] = {
                "amount": authorized,
                "modelId": row["modelId"],
                "phase": row["phase"],
            }
        elif row["recordType"] == "budget_settlement":
            if reservation_id not in reservations:
                raise ValueError("budget settlement has no reservation")
            if reservation_id in settled:
                raise ValueError("budget reservation has duplicate settlements")
            reservation = reservations[reservation_id]
            debit = float(row["budgetDebitEur"])
            if (
                row["modelId"] != reservation["modelId"]
                or row["phase"] != reservation["phase"]
                or not 0 <= debit <= reservation["amount"]
            ):
                raise ValueError("budget settlement does not match its reservation")
            reservation["amount"] = debit
            settled.add(reservation_id)
        else:
            raise ValueError("unknown frontier budget record type")
    return round(sum(float(item["amount"]) for item in reservations.values()), 9)


def reserve_budget(
    ledger_path: Path,
    *,
    model_id: str,
    phase: str,
    authorized_cost_eur: float,
    total_authorized_cost_eur: float,
) -> tuple[str, float]:
    if authorized_cost_eur <= 0 or authorized_cost_eur > total_authorized_cost_eur:
        raise ValueError("budget reservation is outside the total authorization")
    current = committed_budget_eur(read_jsonl(ledger_path))
    if current + authorized_cost_eur > total_authorized_cost_eur:
        raise RuntimeError("OPENROUTER_FRONTIER_EUR_10_BUDGET_EXHAUSTED")
    reservation_id = str(uuid.uuid4())
    append_jsonl(
        ledger_path,
        {
            "schemaVersion": "purposebound-finance.frontier-budget.v2",
            "recordType": "budget_reservation",
            "reservationId": reservation_id,
            "recordedAt": datetime.now(UTC).isoformat(),
            "modelId": model_id,
            "phase": phase,
            "authorizedCostEur": authorized_cost_eur,
            "totalAuthorizedCostEur": total_authorized_cost_eur,
            "committedAfterReservationEur": round(current + authorized_cost_eur, 9),
        },
    )
    return reservation_id, round(current + authorized_cost_eur, 9)


def settle_budget(
    ledger_path: Path,
    *,
    reservation_id: str,
    model_id: str,
    phase: str,
    budget_debit_eur: float,
    outcome: str,
    provider_reported_cost: Mapping[str, Any] | None = None,
) -> float:
    rows = read_jsonl(ledger_path)
    matching = [
        row
        for row in rows
        if row["recordType"] == "budget_reservation"
        and row["reservationId"] == reservation_id
    ]
    if len(matching) != 1:
        raise ValueError("budget reservation is absent or duplicated")
    if any(
        row["recordType"] == "budget_settlement"
        and row["reservationId"] == reservation_id
        for row in rows
    ):
        raise ValueError("budget reservation is already settled")
    authorized = float(matching[0]["authorizedCostEur"])
    if matching[0]["modelId"] != model_id or matching[0]["phase"] != phase:
        raise ValueError("budget settlement does not match its reservation")
    if not 0 <= budget_debit_eur <= authorized:
        raise ValueError("budget settlement exceeds its reservation")
    append_jsonl(
        ledger_path,
        {
            "schemaVersion": "purposebound-finance.frontier-budget.v2",
            "recordType": "budget_settlement",
            "reservationId": reservation_id,
            "recordedAt": datetime.now(UTC).isoformat(),
            "modelId": model_id,
            "phase": phase,
            "budgetDebitEur": budget_debit_eur,
            "providerReportedCost": (
                dict(provider_reported_cost)
                if provider_reported_cost is not None
                else None
            ),
            "outcome": outcome,
        },
    )
    return committed_budget_eur(read_jsonl(ledger_path))
