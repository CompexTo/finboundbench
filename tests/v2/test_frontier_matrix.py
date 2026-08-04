import json
from pathlib import Path

import pytest

from purposebench.v2.frontier_matrix import (
    committed_budget_eur,
    load_frontier_matrix,
    reserve_budget,
    settle_budget,
)


def test_frontier_matrix_pins_six_required_model_families() -> None:
    config, models = load_frontier_matrix(
        Path.cwd(),
        Path("configs/v2/openrouter-frontier-matrix.json").resolve(),
    )
    ids = [model["modelId"] for model in models]
    assert ids == config["modelIds"]
    assert len(ids) == 6
    assert any("gpt-5.6-luna" in model_id for model_id in ids)
    assert any("claude-opus-5" in model_id for model_id in ids)
    assert any("deepseek-v4" in model_id for model_id in ids)
    assert any("kimi-k3" in model_id for model_id in ids)
    assert all(
        {"response_format", "structured_outputs"}.issubset(model["supportedParameters"])
        and {"max_tokens", "max_completion_tokens"}.intersection(
            model["supportedParameters"]
        )
        for model in models
    )
    assert config["phases"]["smoke"] == {"pairLimit": 1, "recordLimit": 1}
    assert config["phases"]["pilot"] == {"pairLimit": 20, "recordLimit": None}


def test_budget_ledger_reserves_before_call_and_settles_down(tmp_path: Path) -> None:
    ledger = tmp_path / "budget.jsonl"
    first, _ = reserve_budget(
        ledger,
        model_id="provider/model-a",
        phase="smoke",
        authorized_cost_eur=0.5,
        total_authorized_cost_eur=1.0,
    )
    second, committed = reserve_budget(
        ledger,
        model_id="provider/model-b",
        phase="smoke",
        authorized_cost_eur=0.5,
        total_authorized_cost_eur=1.0,
    )
    assert committed == 1.0
    assert settle_budget(
        ledger,
        reservation_id=first,
        model_id="provider/model-a",
        phase="smoke",
        budget_debit_eur=0.1,
        outcome="passed",
    ) == 0.6
    assert committed_budget_eur(
        [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    ) == 0.6
    with pytest.raises(ValueError, match="already settled"):
        settle_budget(
            ledger,
            reservation_id=first,
            model_id="provider/model-a",
            phase="smoke",
            budget_debit_eur=0.1,
            outcome="passed",
        )
    assert second


def test_budget_ledger_rejects_mismatched_or_duplicate_settlement() -> None:
    rows = [
        {
            "recordType": "budget_reservation",
            "reservationId": "r1",
            "modelId": "provider/model-a",
            "phase": "smoke",
            "authorizedCostEur": 0.5,
        },
        {
            "recordType": "budget_settlement",
            "reservationId": "r1",
            "modelId": "provider/model-b",
            "phase": "smoke",
            "budgetDebitEur": 0.1,
        },
    ]
    with pytest.raises(ValueError, match="does not match"):
        committed_budget_eur(rows)


def test_budget_ledger_fails_closed_at_total_cap(tmp_path: Path) -> None:
    ledger = tmp_path / "budget.jsonl"
    reserve_budget(
        ledger,
        model_id="provider/model-a",
        phase="pilot",
        authorized_cost_eur=0.6,
        total_authorized_cost_eur=1.0,
    )
    with pytest.raises(RuntimeError, match="BUDGET_EXHAUSTED"):
        reserve_budget(
            ledger,
            model_id="provider/model-b",
            phase="pilot",
            authorized_cost_eur=0.5,
            total_authorized_cost_eur=1.0,
        )
