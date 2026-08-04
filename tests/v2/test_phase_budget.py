from pathlib import Path

import pytest

from purposebench.v2.phase_budget import (
    committed_category_eur,
    reserve_phase_budget,
    settle_phase_budget,
)


def test_phase_budget_enforces_category_and_absolute_caps(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    reservation, global_reserved, category_reserved = reserve_phase_budget(
        ledger,
        model_id="anthropic/claude-opus-5",
        phase="claude_gate_1",
        category="new_claude_compatibility",
        authorization_id="phase2-20260805",
        authorized_cost_eur=0.5,
        category_authorized_eur=1.5,
        absolute_authorized_eur=5,
    )
    assert global_reserved == 0.5
    assert category_reserved == 0.5
    global_settled, category_settled = settle_phase_budget(
        ledger,
        reservation_id=reservation,
        model_id="anthropic/claude-opus-5",
        phase="claude_gate_1",
        category="new_claude_compatibility",
        authorization_id="phase2-20260805",
        budget_debit_eur=0.02,
        outcome="passed",
        provider_reported_cost={"amount": 0.01, "unit": "OPENROUTER_CREDITS"},
    )
    assert global_settled == 0.02
    assert category_settled == 0.02
    assert committed_category_eur([], "new_claude_compatibility") == 0

    with pytest.raises(RuntimeError, match="CATEGORY"):
        reserve_phase_budget(
            ledger,
            model_id="anthropic/claude-opus-5",
            phase="claude_gate_2",
            category="new_claude_compatibility",
            authorization_id="phase2-20260805",
            authorized_cost_eur=1.49,
            category_authorized_eur=1.5,
            absolute_authorized_eur=5,
        )


def test_phase_budget_preserves_failed_reservation(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    reservation, _, _ = reserve_phase_budget(
        ledger,
        model_id="anthropic/claude-opus-5",
        phase="claude_gate_1",
        category="new_claude_compatibility",
        authorization_id="phase2-20260805",
        authorized_cost_eur=0.5,
        category_authorized_eur=1.5,
        absolute_authorized_eur=5,
    )
    _, category = settle_phase_budget(
        ledger,
        reservation_id=reservation,
        model_id="anthropic/claude-opus-5",
        phase="claude_gate_1",
        category="new_claude_compatibility",
        authorization_id="phase2-20260805",
        budget_debit_eur=0.5,
        outcome="failed_conservative_debit",
    )
    assert category == 0.5
