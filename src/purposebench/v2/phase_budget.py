"""Category-scoped reservations on the append-only OpenRouter ledger."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import append_jsonl, read_jsonl
from purposebench.v2.frontier_matrix import committed_budget_eur


def committed_category_eur(
    rows: Sequence[Mapping[str, Any]],
    category: str,
) -> float:
    reservations: dict[str, float] = {}
    for row in rows:
        if row.get("budgetCategory") != category:
            continue
        reservation_id = str(row.get("reservationId", ""))
        if row.get("recordType") == "budget_reservation":
            if reservation_id in reservations:
                raise ValueError("duplicate categorized budget reservation")
            reservations[reservation_id] = float(row["authorizedCostEur"])
        elif row.get("recordType") == "budget_settlement":
            if reservation_id not in reservations:
                raise ValueError("categorized settlement has no reservation")
            debit = float(row["budgetDebitEur"])
            if not 0 <= debit <= reservations[reservation_id]:
                raise ValueError("categorized settlement exceeds its reservation")
            reservations[reservation_id] = debit
    return round(sum(reservations.values()), 9)


def reserve_phase_budget(
    ledger_path: Path,
    *,
    model_id: str,
    phase: str,
    category: str,
    authorization_id: str,
    authorized_cost_eur: float,
    category_authorized_eur: float,
    absolute_authorized_eur: float,
) -> tuple[str, float, float]:
    if not 0 < authorized_cost_eur <= category_authorized_eur:
        raise ValueError("phase reservation is outside its category authorization")
    rows = read_jsonl(ledger_path)
    global_committed = committed_budget_eur(rows)
    category_committed = committed_category_eur(rows, category)
    if global_committed + authorized_cost_eur > absolute_authorized_eur:
        raise RuntimeError("OPENROUTER_ABSOLUTE_BUDGET_EXHAUSTED")
    if category_committed + authorized_cost_eur > category_authorized_eur:
        raise RuntimeError("OPENROUTER_CATEGORY_BUDGET_EXHAUSTED")
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
            "budgetCategory": category,
            "authorizationId": authorization_id,
            "authorizedCostEur": authorized_cost_eur,
            "categoryAuthorizedCostEur": category_authorized_eur,
            "absoluteAuthorizedCostEur": absolute_authorized_eur,
            "committedAfterReservationEur": round(
                global_committed + authorized_cost_eur,
                9,
            ),
            "categoryCommittedAfterReservationEur": round(
                category_committed + authorized_cost_eur,
                9,
            ),
        },
    )
    return (
        reservation_id,
        round(global_committed + authorized_cost_eur, 9),
        round(category_committed + authorized_cost_eur, 9),
    )


def settle_phase_budget(
    ledger_path: Path,
    *,
    reservation_id: str,
    model_id: str,
    phase: str,
    category: str,
    authorization_id: str,
    budget_debit_eur: float,
    outcome: str,
    provider_reported_cost: Mapping[str, Any] | None = None,
) -> tuple[float, float]:
    rows = read_jsonl(ledger_path)
    matches = [
        row
        for row in rows
        if row.get("recordType") == "budget_reservation"
        and row.get("reservationId") == reservation_id
    ]
    if len(matches) != 1:
        raise ValueError("phase budget reservation is absent or duplicated")
    reservation = matches[0]
    if any(
        row.get("recordType") == "budget_settlement"
        and row.get("reservationId") == reservation_id
        for row in rows
    ):
        raise ValueError("phase budget reservation is already settled")
    if (
        reservation.get("modelId") != model_id
        or reservation.get("phase") != phase
        or reservation.get("budgetCategory") != category
        or reservation.get("authorizationId") != authorization_id
        or not 0 <= budget_debit_eur <= float(reservation["authorizedCostEur"])
    ):
        raise ValueError("phase settlement does not match its reservation")
    append_jsonl(
        ledger_path,
        {
            "schemaVersion": "purposebound-finance.frontier-budget.v2",
            "recordType": "budget_settlement",
            "reservationId": reservation_id,
            "recordedAt": datetime.now(UTC).isoformat(),
            "modelId": model_id,
            "phase": phase,
            "budgetCategory": category,
            "authorizationId": authorization_id,
            "budgetDebitEur": budget_debit_eur,
            "providerReportedCost": (
                dict(provider_reported_cost)
                if provider_reported_cost is not None
                else None
            ),
            "outcome": outcome,
        },
    )
    updated = read_jsonl(ledger_path)
    return committed_budget_eur(updated), committed_category_eur(updated, category)
