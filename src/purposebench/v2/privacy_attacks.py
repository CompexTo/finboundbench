"""Controlled empirical privacy-attack measurements for protocol-v2-local.

These measurements characterize observed attack performance. They are not
proofs, and a low score does not establish that a mechanism prevents every
form of data leakage.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

REQUIRED_CONDITIONS = (
    "ordinary",
    "governed_non_dp",
    "governed_dp",
)

PRIVACY_ATTACK_LIMITATIONS = (
    "These are empirical attacks against specified observations, not universal guarantees.",
    "Governance controls access and evidence but does not by itself provide differential privacy.",
    "Differential privacy bounds a declared adjacency and release process; it does not prevent every leakage mode.",
    "Repeated-query and differencing results depend on whether releases share or independently consume budget.",
    "Aggregate reconstruction is meaningful only when the query system is sufficiently informative.",
)


@dataclass(frozen=True)
class AttackMeasurement:
    attack: str
    condition: str
    meaningful: bool
    risk_score: float | None
    metrics: Mapping[str, float | int | bool]
    utility: Mapping[str, float] = field(default_factory=dict)
    limitations: tuple[str, ...] = PRIVACY_ATTACK_LIMITATIONS


@dataclass(frozen=True)
class AttackComparison:
    attack: str
    ordinary_risk: float
    governed_non_dp_risk: float
    governed_dp_risk: float
    governance_only_risk_change: float
    dp_risk_reduction_vs_ordinary: float
    dp_risk_reduction_vs_governed_non_dp: float


@dataclass(frozen=True)
class PrivacyAttackReport:
    measurements: tuple[AttackMeasurement, ...]
    comparisons: tuple[AttackComparison, ...]
    limitations: tuple[str, ...] = PRIVACY_ATTACK_LIMITATIONS


@dataclass(frozen=True)
class ConditionAttackInputs:
    """Optional observations for each controlled attack under one condition."""

    utility: Mapping[str, float] = field(default_factory=dict)
    member_losses: Sequence[float] | None = None
    nonmember_losses: Sequence[float] | None = None
    sensitive_truth: Sequence[str] | None = None
    sensitive_predictions: Sequence[str] | None = None
    repeated_query_truth: float | None = None
    repeated_query_answers: Sequence[float] | None = None
    differencing_with_record: float | None = None
    differencing_without_record: float | None = None
    differencing_true_contribution: float | None = None
    reconstruction_queries: Sequence[Sequence[float]] | None = None
    reconstruction_answers: Sequence[float] | None = None
    reconstruction_truth: Sequence[int] | None = None


def _finite_1d(
    values: Sequence[float],
    name: str,
    *,
    minimum: int = 1,
) -> np.ndarray[Any, Any]:
    array = np.asarray(values, dtype=float)
    if (
        array.ndim != 1
        or len(array) < minimum
        or not np.all(np.isfinite(array))
    ):
        raise ValueError(
            f"{name} must be a finite one-dimensional sequence"
        )
    return array


def _normalized_advantage(score: float, baseline: float) -> float:
    if baseline >= 1.0:
        return 0.0
    return float(
        np.clip(
            (score - baseline) / (1.0 - baseline),
            0.0,
            1.0,
        )
    )


def classification_utility(
    truth: Sequence[int | str],
    predictions: Sequence[int | str],
) -> dict[str, float]:
    """Return deterministic accuracy and macro-recall utility metrics."""

    true = np.asarray(truth, dtype=object)
    predicted = np.asarray(predictions, dtype=object)
    if (
        true.ndim != 1
        or predicted.shape != true.shape
        or len(true) == 0
    ):
        raise ValueError(
            "truth and predictions must be matching nonempty sequences"
        )
    labels = sorted(set(true.tolist()), key=str)
    recalls = [
        float(np.mean(predicted[true == label] == label))
        for label in labels
    ]
    return {
        "accuracy": float(np.mean(predicted == true)),
        "balanced_accuracy": float(np.mean(recalls)),
    }


def membership_inference_attack(
    member_losses: Sequence[float],
    nonmember_losses: Sequence[float],
    *,
    condition: str,
    utility: Mapping[str, float] | None = None,
) -> AttackMeasurement:
    """Measure a calibrated loss-threshold membership attack."""

    members = _finite_1d(member_losses, "member_losses")
    nonmembers = _finite_1d(nonmember_losses, "nonmember_losses")
    pair_scores = [
        1.0
        if member < nonmember
        else 0.5
        if member == nonmember
        else 0.0
        for member in members
        for nonmember in nonmembers
    ]
    directional_auc = float(np.mean(pair_scores))
    calibrated_auc = max(directional_auc, 1.0 - directional_auc)
    candidates = sorted(
        set(np.concatenate([members, nonmembers]).tolist())
    )
    thresholds = [float("-inf"), *candidates, float("inf")]
    best_balanced_accuracy = 0.5
    for threshold in thresholds:
        member_recall = float(np.mean(members <= threshold))
        nonmember_recall = float(np.mean(nonmembers > threshold))
        best_balanced_accuracy = max(
            best_balanced_accuracy,
            (member_recall + nonmember_recall) / 2.0,
        )
    advantage = _normalized_advantage(
        best_balanced_accuracy,
        0.5,
    )
    return AttackMeasurement(
        attack="membership_inference",
        condition=condition,
        meaningful=True,
        risk_score=advantage,
        metrics={
            "calibrated_roc_auc": calibrated_auc,
            "best_balanced_accuracy": best_balanced_accuracy,
            "membership_advantage": advantage,
            "member_samples": len(members),
            "nonmember_samples": len(nonmembers),
        },
        utility=dict(utility or {}),
    )


def attribute_inference_attack(
    truth: Sequence[str],
    predictions: Sequence[str],
    *,
    condition: str,
    utility: Mapping[str, float] | None = None,
) -> AttackMeasurement:
    """Measure sensitive-attribute inference over a declared test sample."""

    metrics = classification_utility(truth, predictions)
    true = np.asarray(truth, dtype=object)
    labels = set(true.tolist())
    counts = [int(np.sum(true == label)) for label in labels]
    majority_baseline = max(counts) / len(true)
    advantage = _normalized_advantage(
        metrics["accuracy"],
        majority_baseline,
    )
    meaningful = len(labels) > 1
    return AttackMeasurement(
        attack="attribute_inference",
        condition=condition,
        meaningful=meaningful,
        risk_score=advantage if meaningful else None,
        metrics={
            **metrics,
            "majority_baseline": majority_baseline,
            "attribute_advantage": advantage,
            "samples": len(true),
        },
        utility=dict(utility or {}),
    )


def repeated_query_averaging_attack(
    true_value: float,
    answers: Sequence[float],
    *,
    condition: str,
    sensitivity_scale: float = 1.0,
    success_tolerance: float = 0.1,
    utility: Mapping[str, float] | None = None,
) -> AttackMeasurement:
    """Measure error reduction obtained by averaging repeated releases."""

    if (
        not math.isfinite(true_value)
        or not math.isfinite(sensitivity_scale)
        or sensitivity_scale <= 0
        or success_tolerance < 0
    ):
        raise ValueError(
            "truth, sensitivity_scale, and success_tolerance are invalid"
        )
    observed = _finite_1d(answers, "answers", minimum=2)
    single_error = abs(float(observed[0]) - true_value)
    averaged = float(np.mean(observed))
    averaged_error = abs(averaged - true_value)
    reduction = single_error - averaged_error
    risk = float(
        np.clip(
            1.0 - averaged_error / sensitivity_scale,
            0.0,
            1.0,
        )
    )
    return AttackMeasurement(
        attack="repeated_query_averaging",
        condition=condition,
        meaningful=True,
        risk_score=risk,
        metrics={
            "queries": len(observed),
            "single_query_absolute_error": single_error,
            "averaged_absolute_error": averaged_error,
            "absolute_error_reduction": reduction,
            "success": averaged_error <= success_tolerance,
        },
        utility=dict(utility or {}),
    )


def differencing_attack(
    with_record_answer: float,
    without_record_answer: float,
    true_contribution: float,
    *,
    condition: str,
    sensitivity_scale: float = 1.0,
    success_tolerance: float = 0.1,
    utility: Mapping[str, float] | None = None,
) -> AttackMeasurement:
    """Measure recovery of one contribution from overlapping releases."""

    values = (
        with_record_answer,
        without_record_answer,
        true_contribution,
    )
    if (
        not all(math.isfinite(value) for value in values)
        or not math.isfinite(sensitivity_scale)
        or sensitivity_scale <= 0
    ):
        raise ValueError(
            "differencing inputs and sensitivity_scale must be finite"
        )
    inferred = with_record_answer - without_record_answer
    error = abs(inferred - true_contribution)
    risk = float(
        np.clip(
            1.0 - error / sensitivity_scale,
            0.0,
            1.0,
        )
    )
    return AttackMeasurement(
        attack="differencing",
        condition=condition,
        meaningful=True,
        risk_score=risk,
        metrics={
            "inferred_contribution": inferred,
            "absolute_error": error,
            "success": error <= success_tolerance,
        },
        utility=dict(utility or {}),
    )


def aggregate_reconstruction_attack(
    query_matrix: Sequence[Sequence[float]],
    answers: Sequence[float],
    truth: Sequence[int],
    *,
    condition: str,
    utility: Mapping[str, float] | None = None,
) -> AttackMeasurement:
    """Attempt binary reconstruction from a linear aggregate query system."""

    matrix = np.asarray(query_matrix, dtype=float)
    observed = _finite_1d(answers, "answers")
    actual = np.asarray(truth, dtype=float)
    if (
        matrix.ndim != 2
        or matrix.shape[0] != len(observed)
        or matrix.shape[1] != len(actual)
    ):
        raise ValueError(
            "query matrix, answers, and truth dimensions do not align"
        )
    if (
        not np.all(np.isfinite(matrix))
        or not np.all(np.isin(actual, [0.0, 1.0]))
    ):
        raise ValueError(
            "queries must be finite and reconstruction truth must be binary"
        )
    rank = int(np.linalg.matrix_rank(matrix))
    meaningful = (
        matrix.shape[0] >= matrix.shape[1]
        and rank == matrix.shape[1]
    )
    common: dict[str, float | int | bool] = {
        "queries": matrix.shape[0],
        "variables": matrix.shape[1],
        "matrix_rank": rank,
        "full_column_rank": meaningful,
    }
    if not meaningful:
        return AttackMeasurement(
            attack="aggregate_reconstruction",
            condition=condition,
            meaningful=False,
            risk_score=None,
            metrics=common,
            utility=dict(utility or {}),
        )
    estimate, *_ = np.linalg.lstsq(matrix, observed, rcond=None)
    clipped = np.clip(estimate, 0.0, 1.0)
    reconstructed = clipped >= 0.5
    accuracy = float(
        np.mean(reconstructed == actual.astype(bool))
    )
    rmse = float(
        np.sqrt(np.mean((clipped - actual) ** 2))
    )
    majority_baseline = max(
        float(np.mean(actual)),
        1.0 - float(np.mean(actual)),
    )
    advantage = _normalized_advantage(
        accuracy,
        majority_baseline,
    )
    return AttackMeasurement(
        attack="aggregate_reconstruction",
        condition=condition,
        meaningful=True,
        risk_score=advantage,
        metrics={
            **common,
            "reconstruction_accuracy": accuracy,
            "reconstruction_rmse": rmse,
            "majority_baseline": majority_baseline,
            "reconstruction_advantage": advantage,
        },
        utility=dict(utility or {}),
    )


def evaluate_privacy_attacks(
    conditions: Mapping[str, ConditionAttackInputs],
) -> PrivacyAttackReport:
    """Evaluate available attacks for the three required conditions."""

    missing = sorted(set(REQUIRED_CONDITIONS) - set(conditions))
    extra = sorted(set(conditions) - set(REQUIRED_CONDITIONS))
    if missing or extra:
        raise ValueError(
            f"conditions must be exactly {REQUIRED_CONDITIONS}; "
            f"missing={missing}, extra={extra}"
        )

    measurements: list[AttackMeasurement] = []
    for condition in REQUIRED_CONDITIONS:
        data = conditions[condition]
        utility = dict(data.utility)
        if (
            data.member_losses is not None
            or data.nonmember_losses is not None
        ):
            if (
                data.member_losses is None
                or data.nonmember_losses is None
            ):
                raise ValueError(
                    "membership attack requires both loss sequences"
                )
            measurements.append(
                membership_inference_attack(
                    data.member_losses,
                    data.nonmember_losses,
                    condition=condition,
                    utility=utility,
                )
            )
        if (
            data.sensitive_truth is not None
            or data.sensitive_predictions is not None
        ):
            if (
                data.sensitive_truth is None
                or data.sensitive_predictions is None
            ):
                raise ValueError(
                    "attribute attack requires truth and predictions"
                )
            measurements.append(
                attribute_inference_attack(
                    data.sensitive_truth,
                    data.sensitive_predictions,
                    condition=condition,
                    utility=utility,
                )
            )
        if (
            data.repeated_query_answers is not None
            or data.repeated_query_truth is not None
        ):
            if (
                data.repeated_query_answers is None
                or data.repeated_query_truth is None
            ):
                raise ValueError(
                    "repeated-query attack requires truth and answers"
                )
            measurements.append(
                repeated_query_averaging_attack(
                    data.repeated_query_truth,
                    data.repeated_query_answers,
                    condition=condition,
                    utility=utility,
                )
            )
        difference_values = (
            data.differencing_with_record,
            data.differencing_without_record,
            data.differencing_true_contribution,
        )
        if any(value is not None for value in difference_values):
            if not all(value is not None for value in difference_values):
                raise ValueError(
                    "differencing attack requires all three values"
                )
            assert data.differencing_with_record is not None
            assert data.differencing_without_record is not None
            assert data.differencing_true_contribution is not None
            measurements.append(
                differencing_attack(
                    data.differencing_with_record,
                    data.differencing_without_record,
                    data.differencing_true_contribution,
                    condition=condition,
                    utility=utility,
                )
            )
        reconstruction_values: tuple[Any, ...] = (
            data.reconstruction_queries,
            data.reconstruction_answers,
            data.reconstruction_truth,
        )
        if any(value is not None for value in reconstruction_values):
            if not all(
                value is not None for value in reconstruction_values
            ):
                raise ValueError(
                    "reconstruction attack requires queries, answers, "
                    "and truth"
                )
            assert data.reconstruction_queries is not None
            assert data.reconstruction_answers is not None
            assert data.reconstruction_truth is not None
            measurements.append(
                aggregate_reconstruction_attack(
                    data.reconstruction_queries,
                    data.reconstruction_answers,
                    data.reconstruction_truth,
                    condition=condition,
                    utility=utility,
                )
            )

    by_attack: dict[str, dict[str, AttackMeasurement]] = {}
    for measurement in measurements:
        if measurement.meaningful and measurement.risk_score is not None:
            by_attack.setdefault(
                measurement.attack,
                {},
            )[measurement.condition] = measurement
    comparisons: list[AttackComparison] = []
    for attack in sorted(by_attack):
        rows = by_attack[attack]
        if set(rows) != set(REQUIRED_CONDITIONS):
            continue
        ordinary_risk = rows["ordinary"].risk_score
        governed_risk = rows["governed_non_dp"].risk_score
        private_risk = rows["governed_dp"].risk_score
        assert ordinary_risk is not None
        assert governed_risk is not None
        assert private_risk is not None
        ordinary = float(ordinary_risk)
        governed = float(governed_risk)
        private = float(private_risk)
        comparisons.append(
            AttackComparison(
                attack=attack,
                ordinary_risk=ordinary,
                governed_non_dp_risk=governed,
                governed_dp_risk=private,
                governance_only_risk_change=governed - ordinary,
                dp_risk_reduction_vs_ordinary=ordinary - private,
                dp_risk_reduction_vs_governed_non_dp=governed - private,
            )
        )
    return PrivacyAttackReport(
        measurements=tuple(measurements),
        comparisons=tuple(comparisons),
    )
