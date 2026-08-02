from __future__ import annotations

import pytest

from purposebench.v2.privacy_attacks import (
    PRIVACY_ATTACK_LIMITATIONS,
    ConditionAttackInputs,
    aggregate_reconstruction_attack,
    classification_utility,
    evaluate_privacy_attacks,
    repeated_query_averaging_attack,
)


def test_attack_helpers_report_utility_and_meaningfulness() -> None:
    utility = classification_utility(
        ["a", "b", "a", "b"],
        ["a", "b", "b", "b"],
    )
    assert utility == {
        "accuracy": 0.75,
        "balanced_accuracy": 0.75,
    }

    averaging = repeated_query_averaging_attack(
        10.0,
        [12.0, 8.0, 10.0],
        condition="governed_dp",
        sensitivity_scale=2.0,
    )
    assert averaging.metrics["absolute_error_reduction"] == 2.0
    assert averaging.metrics["averaged_absolute_error"] == 0.0
    assert averaging.risk_score == 1.0

    underdetermined = aggregate_reconstruction_attack(
        [[1.0, 1.0, 0.0]],
        [1.0],
        [1, 0, 1],
        condition="ordinary",
    )
    assert underdetermined.meaningful is False
    assert underdetermined.risk_score is None
    assert underdetermined.metrics["full_column_rank"] is False


def test_full_attack_report_compares_three_conditions() -> None:
    truth = ["high", "low", "high", "low"]
    query_matrix = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    reconstruction_truth = [0, 1, 0, 1]
    ordinary = ConditionAttackInputs(
        utility={"accuracy": 0.9},
        member_losses=[0.1, 0.2, 0.15, 0.25],
        nonmember_losses=[0.8, 0.9, 0.75, 0.85],
        sensitive_truth=truth,
        sensitive_predictions=truth,
        repeated_query_truth=10.0,
        repeated_query_answers=[10.0, 10.0, 10.0],
        differencing_with_record=11.0,
        differencing_without_record=10.0,
        differencing_true_contribution=1.0,
        reconstruction_queries=query_matrix,
        reconstruction_answers=[0.0, 1.0, 0.0, 1.0],
        reconstruction_truth=reconstruction_truth,
    )
    governed_non_dp = ConditionAttackInputs(
        **{
            **ordinary.__dict__,
            "utility": {"accuracy": 0.88},
        }
    )
    governed_dp = ConditionAttackInputs(
        utility={"accuracy": 0.8},
        member_losses=[0.5, 0.5, 0.5, 0.5],
        nonmember_losses=[0.5, 0.5, 0.5, 0.5],
        sensitive_truth=truth,
        sensitive_predictions=["high", "high", "high", "high"],
        repeated_query_truth=10.0,
        repeated_query_answers=[12.0, 12.0, 12.0],
        differencing_with_record=12.0,
        differencing_without_record=10.0,
        differencing_true_contribution=1.0,
        reconstruction_queries=query_matrix,
        reconstruction_answers=[0.6, 0.4, 0.6, 0.4],
        reconstruction_truth=reconstruction_truth,
    )

    report = evaluate_privacy_attacks(
        {
            "ordinary": ordinary,
            "governed_non_dp": governed_non_dp,
            "governed_dp": governed_dp,
        }
    )

    assert len(report.measurements) == 15
    assert {comparison.attack for comparison in report.comparisons} == {
        "aggregate_reconstruction",
        "attribute_inference",
        "differencing",
        "membership_inference",
        "repeated_query_averaging",
    }
    assert all(
        comparison.governance_only_risk_change == 0.0
        for comparison in report.comparisons
    )
    assert all(
        comparison.dp_risk_reduction_vs_governed_non_dp > 0
        for comparison in report.comparisons
    )
    assert report.limitations == PRIVACY_ATTACK_LIMITATIONS
    assert any(
        "does not prevent every leakage mode" in limitation
        for limitation in report.limitations
    )


def test_report_requires_all_and_only_declared_conditions() -> None:
    with pytest.raises(ValueError, match="conditions must be exactly"):
        evaluate_privacy_attacks(
            {
                "ordinary": ConditionAttackInputs(),
                "governed_non_dp": ConditionAttackInputs(),
            }
        )
