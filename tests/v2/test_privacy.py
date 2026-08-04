from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

import purposebench.v2.privacy as privacy_module
from purposebench.v2.privacy import (
    BudgetPolicyMismatch,
    DifferentialPrivacyEngine,
    DuplicateReleaseError,
    LedgerState,
    MinimumCohortError,
    OptionalPrivacyDependencyError,
    PrivacyBudgetExceeded,
    PrivacyLedger,
    PrivacyLedgerKey,
    PrivacySpec,
    default_dp_training_configs,
    dp_count,
    dp_group_comparison,
    dp_histogram,
    dp_mean,
    dp_rate,
    train_tabular_classifier,
)


class ZeroNoise:
    def __init__(self) -> None:
        self.scales: list[float] = []

    def laplace(self, loc: float, scale: float) -> float:
        assert loc == 0.0
        self.scales.append(scale)
        return 0.0


def _spec(**overrides: Any) -> PrivacySpec:
    values: dict[str, Any] = {
        "mechanism": "LAPLACE",
        "epsilon_target": 1.0,
        "delta": 1e-5,
        "clipping_norm": None,
        "noise_multiplier": None,
        "sample_rate": None,
        "epochs": None,
        "steps": None,
        "accountant": "sequential",
        "dataset_budget": 3.0,
        "purpose_budget": 2.0,
        "release_budget": 1.0,
        "minimum_cohort_size": 2,
        "approved_output_types": (
            "count",
            "mean",
            "histogram",
            "rate",
            "group_comparison",
            "model",
        ),
    }
    values.update(overrides)
    return PrivacySpec(**values)


def _key(release_id: str, contract: str = "a" * 64) -> PrivacyLedgerKey:
    return PrivacyLedgerKey(
        dataset_version_id="dataset-v1",
        purpose="approved-analysis",
        contract_hash=contract,
        release_id=release_id,
    )


def test_privacy_spec_is_immutable_and_validates_dp_sgd() -> None:
    spec = _spec()
    with pytest.raises(ValidationError):
        spec.release_budget = 2.0  # type: ignore[misc]
    assert len(spec.spec_hash) == 64

    with pytest.raises(ValidationError, match="exactly one"):
        _spec(
            mechanism="DP_SGD",
            clipping_norm=1.0,
            noise_multiplier=1.0,
            sample_rate=0.1,
            epochs=5,
            steps=50,
        )
    training = _spec(
        mechanism="DP_SGD",
        clipping_norm=1.0,
        noise_multiplier=1.0,
        sample_rate=0.1,
        epochs=5,
    )
    assert training.epochs == 5
    assert training.steps is None


def test_ledger_reserve_commit_rollback_and_determinism() -> None:
    spec = _spec()
    first = PrivacyLedger()
    reservation = first.reserve(
        _key("release-1"),
        epsilon=0.75,
        delta=0.0,
        output_type="count",
        spec=spec,
    )
    committed = first.commit(
        reservation.reservation_id,
        actual_epsilon=0.5,
        actual_delta=0.0,
    )
    assert committed.state is LedgerState.COMMITTED
    assert committed.epsilon == 0.5
    with pytest.raises(DuplicateReleaseError):
        first.reserve(
            _key("release-1"),
            epsilon=0.1,
            delta=0.0,
            output_type="count",
            spec=spec,
        )

    rolled = first.reserve(
        _key("release-2"),
        epsilon=0.75,
        delta=0.0,
        output_type="mean",
        spec=spec,
    )
    first.rollback(rolled.reservation_id)
    composition = first.composition(
        dataset_version_id="dataset-v1",
        purpose="approved-analysis",
    )
    assert composition.committed_epsilon == 0.5
    assert composition.reserved_epsilon == 0.0
    assert composition.committed_delta == 0.0

    second = PrivacyLedger()
    same = second.reserve(
        _key("release-1"),
        epsilon=0.75,
        delta=0.0,
        output_type="count",
        spec=spec,
    )
    assert same.reservation_id == reservation.reservation_id


def test_ledger_composition_exhaustion_and_locked_policy() -> None:
    ledger = PrivacyLedger()
    spec = _spec()
    for release_id in ("one", "two"):
        reservation = ledger.reserve(
            _key(release_id),
            epsilon=1.0,
            delta=1e-6,
            output_type="count",
            spec=spec,
        )
        ledger.commit(reservation.reservation_id)

    with pytest.raises(PrivacyBudgetExceeded, match="purpose budget exhausted"):
        ledger.reserve(
            _key("three"),
            epsilon=0.1,
            delta=0.0,
            output_type="count",
            spec=spec,
        )

    changed_policy = _spec(dataset_budget=4.0)
    with pytest.raises(BudgetPolicyMismatch, match="dataset budget"):
        ledger.reserve(
            PrivacyLedgerKey(
                dataset_version_id="dataset-v1",
                purpose="another-purpose",
                contract_hash="b" * 64,
                release_id="policy-change",
            ),
            epsilon=0.1,
            delta=0.0,
            output_type="count",
            spec=changed_policy,
        )


def test_ledger_reservations_are_atomic_under_concurrency() -> None:
    ledger = PrivacyLedger()
    spec = _spec(
        dataset_budget=1.0,
        purpose_budget=1.0,
        release_budget=0.75,
        epsilon_target=0.75,
    )

    def attempt(index: int) -> str:
        try:
            ledger.reserve(
                _key(f"concurrent-{index}"),
                epsilon=0.75,
                delta=0.0,
                output_type="count",
                spec=spec,
            )
            return "reserved"
        except PrivacyBudgetExceeded:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert sorted(outcomes) == ["blocked", "reserved"]
    composition = ledger.composition(dataset_version_id="dataset-v1")
    assert composition.reserved_epsilon == 0.75
    assert composition.reserved_releases == 1


def test_deterministic_aggregate_mechanisms_and_minimum_cohort() -> None:
    count_rng = ZeroNoise()
    assert dp_count(
        [1, 2, 3],
        epsilon=1.0,
        minimum_cohort_size=2,
        rng=count_rng,
    ) == 3.0
    assert count_rng.scales == [1.0]

    mean_rng = ZeroNoise()
    assert dp_mean(
        [1.0, 3.0],
        lower=0.0,
        upper=4.0,
        epsilon=1.0,
        minimum_cohort_size=2,
        rng=mean_rng,
    ) == 2.0
    assert mean_rng.scales == [8.0, 2.0]

    histogram = dp_histogram(
        ["a", "b", "a"],
        categories=["a", "b"],
        epsilon=1.0,
        minimum_cohort_size=2,
        rng=ZeroNoise(),
    )
    assert histogram == {"a": 2.0, "b": 1.0}

    rate = dp_rate(
        [True, False, True],
        epsilon=1.0,
        minimum_cohort_size=2,
        rng=ZeroNoise(),
    )
    assert rate == pytest.approx(2 / 3)

    comparison = dp_group_comparison(
        {"b": [2.0, 4.0], "a": [1.0, 3.0]},
        lower=0.0,
        upper=5.0,
        epsilon=2.0,
        minimum_cohort_size=2,
        rng=ZeroNoise(),
    )
    assert comparison["group_means"] == {"a": 2.0, "b": 3.0}
    assert comparison["pairwise_differences"] == {"a-minus-b": -1.0}

    with pytest.raises(MinimumCohortError):
        dp_count(
            [1],
            epsilon=1.0,
            minimum_cohort_size=2,
            rng=ZeroNoise(),
        )


def test_engine_commits_success_and_rolls_back_failed_release() -> None:
    ledger = PrivacyLedger()
    engine = DifferentialPrivacyEngine(
        _spec(),
        ledger,
        rng=ZeroNoise(),
    )
    released = engine.count(
        _key("engine-count"),
        [1, 2, 3],
        epsilon=1.0,
    )
    assert released.value == 3.0
    assert released.ledger_record.state is LedgerState.COMMITTED

    with pytest.raises(MinimumCohortError):
        engine.mean(
            _key("engine-failure"),
            [1.0],
            lower=0.0,
            upper=2.0,
            epsilon=0.5,
        )
    records = ledger.records()
    assert [record.state for record in records] == [
        LedgerState.COMMITTED,
        LedgerState.ROLLED_BACK,
    ]
    composition = ledger.composition(dataset_version_id="dataset-v1")
    assert composition.committed_epsilon == 1.0
    assert composition.reserved_epsilon == 0.0


def test_training_presets_and_clear_optional_dependency_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configs = default_dp_training_configs(seed=7)
    assert [config.name for config in configs] == [
        "non_dp",
        "weak_dp",
        "medium_dp",
        "stronger_dp",
    ]
    assert [config.private for config in configs] == [
        False,
        True,
        True,
        True,
    ]
    noise_multipliers = [
        config.noise_multiplier for config in configs[1:]
        if config.noise_multiplier is not None
    ]
    assert len(noise_multipliers) == 3
    assert noise_multipliers == sorted(noise_multipliers)

    def unavailable() -> Any:
        raise OptionalPrivacyDependencyError(
            "install purposebound-finance[privacy]"
        )

    monkeypatch.setattr(privacy_module, "_load_torch", unavailable)
    with pytest.raises(
        OptionalPrivacyDependencyError,
        match="purposebound-finance",
    ):
        train_tabular_classifier(
            np.zeros((10, 2), dtype=float),
            np.asarray([0, 1] * 5),
            configs[0],
        )


def test_training_rejects_privacy_parameter_substitution_before_execution() -> None:
    private_config = default_dp_training_configs(seed=7)[1]
    mismatched = _spec(
        mechanism="DP_SGD",
        clipping_norm=1.0,
        noise_multiplier=0.8,
        sample_rate=1.0,
        epochs=private_config.epochs,
        accountant=private_config.accountant,
        delta=private_config.delta,
    )
    with pytest.raises(
        ValueError,
        match="noise_multiplier differs",
    ):
        train_tabular_classifier(
            np.zeros((10, 2), dtype=float),
            np.asarray([0, 1] * 5),
            private_config,
            ledger=PrivacyLedger(),
            ledger_key=_key("training"),
            privacy_spec=mismatched,
        )
