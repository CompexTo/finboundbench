"""Cumulative-budget orchestration for the governed OpenRouter frontier matrix."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import append_jsonl, read_jsonl, sha256_json
from purposebench.v2.remote_pilot import validate_remote_model_manifest

BUDGET_LEDGER = Path("results/v2/raw/inference/openrouter-frontier-budget.jsonl")


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
