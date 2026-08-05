"""Append-only v3 OpenRouter budget ledger with reservation and settlement."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import append_jsonl, read_jsonl

LEDGER_SCHEMA = "finboundbench.budget-ledger.v3"
LEDGER_PATH = Path("results/v3/raw/budget/openrouter-v3-ledger.jsonl")


def committed_budget_eur(rows: Sequence[Mapping[str, Any]]) -> float:
    reservations: dict[str, float] = {}
    for row in rows:
        reservation_id = str(row.get("reservationId", ""))
        if row.get("recordType") == "budget_reservation":
            if reservation_id in reservations:
                raise ValueError("duplicate v3 budget reservation")
            reservations[reservation_id] = float(row["authorizedCostEur"])
        elif row.get("recordType") == "budget_settlement":
            if reservation_id not in reservations:
                raise ValueError("v3 settlement has no reservation")
            debit = float(row["budgetDebitEur"])
            if not 0 <= debit <= reservations[reservation_id]:
                raise ValueError("v3 settlement exceeds its reservation")
            reservations[reservation_id] = debit
        elif row.get("recordType") == "budget_reconciliation":
            if reservation_id not in reservations:
                raise ValueError("v3 reconciliation has no reservation")
            previous = float(row["previousBudgetDebitEur"])
            revised = float(row["revisedBudgetDebitEur"])
            if previous != reservations[reservation_id] or not 0 <= revised <= previous:
                raise ValueError("v3 reconciliation is invalid")
            reservations[reservation_id] = revised
        else:
            raise ValueError("unknown v3 budget ledger record type")
    return round(sum(reservations.values()), 9)


def committed_phase_eur(rows: Sequence[Mapping[str, Any]], phase: str) -> float:
    return committed_budget_eur([row for row in rows if row.get("phase") == phase])


def reserve_budget(
    ledger_path: Path,
    *,
    model_id: str,
    phase: str,
    authorization_id: str,
    authorized_cost_eur: float,
    phase_authorized_eur: float,
    absolute_authorized_eur: float,
) -> str:
    if not 0 < authorized_cost_eur <= phase_authorized_eur <= absolute_authorized_eur:
        raise ValueError("v3 budget reservation is outside its authorization envelope")
    rows = read_jsonl(ledger_path)
    if committed_budget_eur(rows) + authorized_cost_eur > absolute_authorized_eur:
        raise RuntimeError("OPENROUTER_V3_ABSOLUTE_BUDGET_EXHAUSTED")
    if committed_phase_eur(rows, phase) + authorized_cost_eur > phase_authorized_eur:
        raise RuntimeError("OPENROUTER_V3_PHASE_BUDGET_EXHAUSTED")
    reservation_id = str(uuid.uuid4())
    append_jsonl(
        ledger_path,
        {
            "schemaVersion": LEDGER_SCHEMA,
            "recordType": "budget_reservation",
            "reservationId": reservation_id,
            "recordedAt": datetime.now(UTC).isoformat(),
            "modelId": model_id,
            "phase": phase,
            "authorizationId": authorization_id,
            "authorizedCostEur": authorized_cost_eur,
            "phaseAuthorizedCostEur": phase_authorized_eur,
            "absoluteAuthorizedCostEur": absolute_authorized_eur,
            "committedAfterReservationEur": round(
                committed_budget_eur(rows) + authorized_cost_eur, 9
            ),
        },
    )
    return reservation_id


def settle_budget(
    ledger_path: Path,
    *,
    reservation_id: str,
    model_id: str,
    phase: str,
    authorization_id: str,
    budget_debit_eur: float,
    outcome: str,
    provider_reported_cost: Mapping[str, Any] | None = None,
) -> float:
    rows = read_jsonl(ledger_path)
    reservations = [
        row
        for row in rows
        if row.get("recordType") == "budget_reservation"
        and row.get("reservationId") == reservation_id
    ]
    if len(reservations) != 1:
        raise ValueError("v3 budget reservation is absent or duplicated")
    reservation = reservations[0]
    if any(
        row.get("recordType") == "budget_settlement"
        and row.get("reservationId") == reservation_id
        for row in rows
    ):
        raise ValueError("v3 budget reservation is already settled")
    if (
        reservation.get("modelId") != model_id
        or reservation.get("phase") != phase
        or reservation.get("authorizationId") != authorization_id
        or not 0 <= budget_debit_eur <= float(reservation["authorizedCostEur"])
    ):
        raise ValueError("v3 settlement does not match its reservation")
    append_jsonl(
        ledger_path,
        {
            "schemaVersion": LEDGER_SCHEMA,
            "recordType": "budget_settlement",
            "reservationId": reservation_id,
            "recordedAt": datetime.now(UTC).isoformat(),
            "modelId": model_id,
            "phase": phase,
            "authorizationId": authorization_id,
            "budgetDebitEur": budget_debit_eur,
            "providerReportedCost": (
                dict(provider_reported_cost) if provider_reported_cost is not None else None
            ),
            "outcome": outcome,
        },
    )
    return committed_budget_eur(read_jsonl(ledger_path))
