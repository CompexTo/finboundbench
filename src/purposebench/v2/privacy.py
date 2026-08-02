"""Local privacy accounting, aggregate mechanisms, and CPU DP training.

The ledger uses conservative sequential composition: epsilons and deltas are
summed. That is deterministic and safe for the supported local experiments,
but it is not a replacement for a durable, transactional platform datastore.
The aggregate mechanisms use add/remove-one adjacency and require bounded
inputs where applicable.
"""

from __future__ import annotations

import hashlib
import math
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Protocol

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from purposebench.utils import canonical_json


class PrivacyError(RuntimeError):
    """Base class for privacy enforcement failures."""


class PrivacyBudgetExceeded(PrivacyError):
    """A reservation would exceed a configured privacy budget."""


class BudgetPolicyMismatch(PrivacyError):
    """A caller tried to change an established scope budget."""


class DuplicateReleaseError(PrivacyError):
    """A release key is already reserved or committed."""


class UnknownReservationError(PrivacyError):
    """A reservation identifier does not exist."""


class InvalidReservationState(PrivacyError):
    """A reservation cannot make the requested state transition."""


class MinimumCohortError(PrivacyError):
    """The protected cohort is smaller than the approved minimum."""


class OptionalPrivacyDependencyError(PrivacyError):
    """The optional Torch/Opacus training dependencies are unavailable."""


class PrivacySpec(BaseModel):
    """Immutable privacy contract shared by analysis and training workloads."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mechanism: str
    epsilon_target: float = Field(gt=0)
    delta: float = Field(ge=0, lt=1)
    clipping_norm: float | None = Field(default=None, gt=0)
    noise_multiplier: float | None = Field(default=None, gt=0)
    sample_rate: float | None = Field(default=None, gt=0, le=1)
    epochs: int | None = Field(default=None, gt=0)
    steps: int | None = Field(default=None, gt=0)
    accountant: str
    dataset_budget: float = Field(gt=0)
    purpose_budget: float = Field(gt=0)
    release_budget: float = Field(gt=0)
    minimum_cohort_size: int = Field(ge=1)
    approved_output_types: tuple[str, ...]

    @field_validator("mechanism", "accountant")
    @classmethod
    def _nonempty_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("identifier must not be empty")
        return normalized

    @field_validator("approved_output_types", mode="before")
    @classmethod
    def _normalize_output_types(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            raise TypeError(
                "approved_output_types must be a sequence, not a string"
            )
        normalized = tuple(str(item).strip() for item in value)
        if not normalized or any(not item for item in normalized):
            raise ValueError("approved_output_types must contain nonempty identifiers")
        if len(set(normalized)) != len(normalized):
            raise ValueError("approved_output_types must not contain duplicates")
        return normalized

    @model_validator(mode="after")
    def _validate_budget_relationships(self) -> PrivacySpec:
        if self.release_budget > self.purpose_budget:
            raise ValueError("release_budget must not exceed purpose_budget")
        if self.purpose_budget > self.dataset_budget:
            raise ValueError("purpose_budget must not exceed dataset_budget")
        if self.mechanism.upper().replace("-", "_") in {"DP_SGD", "DPSGD"}:
            if self.clipping_norm is None or self.noise_multiplier is None:
                raise ValueError("DP-SGD requires clipping_norm and noise_multiplier")
            if self.sample_rate is None:
                raise ValueError("DP-SGD requires sample_rate")
            if (self.epochs is None) == (self.steps is None):
                raise ValueError("DP-SGD requires exactly one of epochs or steps")
        return self

    @property
    def spec_hash(self) -> str:
        body = canonical_json(self.model_dump(mode="json"))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass(frozen=True, order=True)
class PrivacyLedgerKey:
    """Identity of one proposed output release."""

    dataset_version_id: str
    purpose: str
    contract_hash: str
    release_id: str

    def __post_init__(self) -> None:
        for name in ("dataset_version_id", "purpose", "contract_hash", "release_id"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")
        if len(self.contract_hash) != 64 or any(
            char not in "0123456789abcdef" for char in self.contract_hash.lower()
        ):
            raise ValueError("contract_hash must be a SHA-256 hex digest")

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


class LedgerState(StrEnum):
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True)
class PrivacyLedgerEntry:
    sequence: int
    reservation_id: str
    key: PrivacyLedgerKey
    output_type: str
    epsilon: float
    delta: float
    spec_hash: str
    state: LedgerState


@dataclass(frozen=True)
class PrivacyComposition:
    committed_epsilon: float
    reserved_epsilon: float
    committed_delta: float
    reserved_delta: float
    committed_releases: int
    reserved_releases: int

    @property
    def total_epsilon(self) -> float:
        return self.committed_epsilon + self.reserved_epsilon

    @property
    def total_delta(self) -> float:
        return self.committed_delta + self.reserved_delta


@dataclass
class _MutableLedgerEntry:
    sequence: int
    reservation_id: str
    key: PrivacyLedgerKey
    output_type: str
    epsilon: Decimal
    delta: Decimal
    spec_hash: str
    state: LedgerState

    def snapshot(self) -> PrivacyLedgerEntry:
        return PrivacyLedgerEntry(
            sequence=self.sequence,
            reservation_id=self.reservation_id,
            key=self.key,
            output_type=self.output_type,
            epsilon=float(self.epsilon),
            delta=float(self.delta),
            spec_hash=self.spec_hash,
            state=self.state,
        )


def _decimal(value: float | Decimal, name: str, *, allow_zero: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not result.is_finite() or result < 0 or (result == 0 and not allow_zero):
        qualifier = "nonnegative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {qualifier}")
    return result


class PrivacyLedger:
    """Thread-safe in-memory privacy ledger with reserve/commit/rollback.

    Reservations count against all relevant budgets immediately. A commit may
    lower, but never raise, the reserved spend. A rollback releases the
    reservation. Scope limits are locked on first use, preventing callers from
    raising a budget by supplying a different spec later.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sequence = 0
        self._entries: dict[str, _MutableLedgerEntry] = {}
        self._key_index: dict[PrivacyLedgerKey, str] = {}
        self._dataset_limits: dict[str, Decimal] = {}
        self._purpose_limits: dict[tuple[str, str], Decimal] = {}

    def reserve(
        self,
        key: PrivacyLedgerKey,
        *,
        epsilon: float,
        delta: float,
        output_type: str,
        spec: PrivacySpec,
    ) -> PrivacyLedgerEntry:
        requested_epsilon = _decimal(epsilon, "epsilon")
        requested_delta = _decimal(delta, "delta", allow_zero=True)
        release_limit = min(
            _decimal(spec.release_budget, "release_budget"),
            _decimal(spec.epsilon_target, "epsilon_target"),
        )
        if requested_epsilon > release_limit:
            raise PrivacyBudgetExceeded(
                f"release epsilon {requested_epsilon} exceeds limit {release_limit}"
            )
        if requested_delta > _decimal(spec.delta, "spec.delta", allow_zero=True):
            raise PrivacyBudgetExceeded(
                f"release delta {requested_delta} exceeds approved delta {spec.delta}"
            )
        if output_type not in spec.approved_output_types:
            raise PrivacyError(f"output type {output_type!r} is not approved")

        with self._lock:
            existing_id = self._key_index.get(key)
            if existing_id is not None:
                existing = self._entries[existing_id]
                if existing.state in {LedgerState.RESERVED, LedgerState.COMMITTED}:
                    raise DuplicateReleaseError(f"release {key.release_id!r} already exists")

            dataset_limit = _decimal(spec.dataset_budget, "dataset_budget")
            purpose_limit = _decimal(spec.purpose_budget, "purpose_budget")
            self._lock_scope_limit(
                self._dataset_limits,
                key.dataset_version_id,
                dataset_limit,
                "dataset",
            )
            purpose_scope = (key.dataset_version_id, key.purpose)
            self._lock_scope_limit(
                self._purpose_limits,
                purpose_scope,
                purpose_limit,
                "purpose",
            )

            dataset_spend = self._scope_epsilon(key.dataset_version_id)
            purpose_spend = self._scope_epsilon(key.dataset_version_id, key.purpose)
            if dataset_spend + requested_epsilon > dataset_limit:
                raise PrivacyBudgetExceeded(
                    "dataset budget exhausted: "
                    f"{dataset_spend} + {requested_epsilon} > {dataset_limit}"
                )
            if purpose_spend + requested_epsilon > purpose_limit:
                raise PrivacyBudgetExceeded(
                    "purpose budget exhausted: "
                    f"{purpose_spend} + {requested_epsilon} > {purpose_limit}"
                )

            self._sequence += 1
            identity = {
                "sequence": self._sequence,
                "key": key.as_dict(),
                "epsilon": str(requested_epsilon),
                "delta": str(requested_delta),
                "output_type": output_type,
                "spec_hash": spec.spec_hash,
            }
            reservation_id = hashlib.sha256(
                canonical_json(identity).encode("utf-8")
            ).hexdigest()
            entry = _MutableLedgerEntry(
                sequence=self._sequence,
                reservation_id=reservation_id,
                key=key,
                output_type=output_type,
                epsilon=requested_epsilon,
                delta=requested_delta,
                spec_hash=spec.spec_hash,
                state=LedgerState.RESERVED,
            )
            self._entries[reservation_id] = entry
            self._key_index[key] = reservation_id
            return entry.snapshot()

    def commit(
        self,
        reservation_id: str,
        *,
        actual_epsilon: float | None = None,
        actual_delta: float | None = None,
    ) -> PrivacyLedgerEntry:
        with self._lock:
            entry = self._entry(reservation_id)
            if entry.state is not LedgerState.RESERVED:
                raise InvalidReservationState(
                    f"cannot commit reservation in state {entry.state}"
                )
            epsilon = (
                entry.epsilon
                if actual_epsilon is None
                else _decimal(actual_epsilon, "actual_epsilon")
            )
            delta = (
                entry.delta
                if actual_delta is None
                else _decimal(actual_delta, "actual_delta", allow_zero=True)
            )
            if epsilon > entry.epsilon or delta > entry.delta:
                raise PrivacyBudgetExceeded(
                    "actual privacy spend exceeds the reserved amount"
                )
            entry.epsilon = epsilon
            entry.delta = delta
            entry.state = LedgerState.COMMITTED
            return entry.snapshot()

    def rollback(self, reservation_id: str) -> PrivacyLedgerEntry:
        with self._lock:
            entry = self._entry(reservation_id)
            if entry.state is not LedgerState.RESERVED:
                raise InvalidReservationState(
                    f"cannot roll back reservation in state {entry.state}"
                )
            entry.state = LedgerState.ROLLED_BACK
            return entry.snapshot()

    def composition(
        self,
        *,
        dataset_version_id: str,
        purpose: str | None = None,
        contract_hash: str | None = None,
    ) -> PrivacyComposition:
        with self._lock:
            matching = [
                entry
                for entry in self._entries.values()
                if entry.key.dataset_version_id == dataset_version_id
                and (purpose is None or entry.key.purpose == purpose)
                and (contract_hash is None or entry.key.contract_hash == contract_hash)
            ]
            committed = [
                item for item in matching if item.state is LedgerState.COMMITTED
            ]
            reserved = [item for item in matching if item.state is LedgerState.RESERVED]
            return PrivacyComposition(
                committed_epsilon=float(
                    sum((item.epsilon for item in committed), Decimal(0))
                ),
                reserved_epsilon=float(
                    sum((item.epsilon for item in reserved), Decimal(0))
                ),
                committed_delta=float(
                    sum((item.delta for item in committed), Decimal(0))
                ),
                reserved_delta=float(
                    sum((item.delta for item in reserved), Decimal(0))
                ),
                committed_releases=len(committed),
                reserved_releases=len(reserved),
            )

    def records(self) -> tuple[PrivacyLedgerEntry, ...]:
        with self._lock:
            return tuple(
                entry.snapshot()
                for entry in sorted(
                    self._entries.values(), key=lambda item: item.sequence
                )
            )

    def _entry(self, reservation_id: str) -> _MutableLedgerEntry:
        try:
            return self._entries[reservation_id]
        except KeyError as exc:
            raise UnknownReservationError(reservation_id) from exc

    @staticmethod
    def _lock_scope_limit(
        limits: dict[Any, Decimal],
        scope: Any,
        requested: Decimal,
        label: str,
    ) -> None:
        existing = limits.get(scope)
        if existing is not None and existing != requested:
            raise BudgetPolicyMismatch(
                f"{label} budget is already fixed at {existing}, not {requested}"
            )
        limits.setdefault(scope, requested)

    def _scope_epsilon(
        self, dataset_version_id: str, purpose: str | None = None
    ) -> Decimal:
        return sum(
            (
                entry.epsilon
                for entry in self._entries.values()
                if entry.state in {LedgerState.RESERVED, LedgerState.COMMITTED}
                and entry.key.dataset_version_id == dataset_version_id
                and (purpose is None or entry.key.purpose == purpose)
            ),
            Decimal(0),
        )


class LaplaceRng(Protocol):
    def laplace(self, loc: float, scale: float) -> Any: ...


def _validate_epsilon(epsilon: float) -> float:
    if not math.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("epsilon must be finite and positive")
    return float(epsilon)


def _validate_cohort(size: int, minimum_cohort_size: int) -> None:
    if minimum_cohort_size < 1:
        raise ValueError("minimum_cohort_size must be at least one")
    if size < minimum_cohort_size:
        raise MinimumCohortError(
            f"cohort size {size} is below minimum {minimum_cohort_size}"
        )


def _noise(rng: LaplaceRng | None, scale: float) -> float:
    generator = rng if rng is not None else np.random.default_rng()
    return float(generator.laplace(0.0, scale))


def _bounded_values(
    values: Sequence[float],
    lower: float,
    upper: float,
    minimum_cohort_size: int,
) -> np.ndarray[Any, np.dtype[np.float64]]:
    if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
        raise ValueError("lower and upper must be finite with lower < upper")
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or not np.all(np.isfinite(array)):
        raise ValueError("values must be a finite one-dimensional sequence")
    _validate_cohort(len(array), minimum_cohort_size)
    return np.clip(array, lower, upper)


def dp_count(
    records: Sequence[Any],
    *,
    epsilon: float,
    minimum_cohort_size: int,
    rng: LaplaceRng | None = None,
) -> float:
    """Release a nonnegative Laplace-noised count (sensitivity one)."""

    epsilon = _validate_epsilon(epsilon)
    _validate_cohort(len(records), minimum_cohort_size)
    return max(0.0, float(len(records)) + _noise(rng, 1.0 / epsilon))


def dp_mean(
    values: Sequence[float],
    *,
    lower: float,
    upper: float,
    epsilon: float,
    minimum_cohort_size: int,
    rng: LaplaceRng | None = None,
) -> float:
    """Release a bounded mean using noisy shifted sum and noisy count.

    Epsilon is split equally between a range-bounded sum and a count. The
    result is clamped to the approved bounds as post-processing.
    """

    epsilon = _validate_epsilon(epsilon)
    clipped = _bounded_values(values, lower, upper, minimum_cohort_size)
    half_epsilon = epsilon / 2.0
    value_range = upper - lower
    shifted_sum = float(np.sum(clipped - lower))
    noisy_sum = shifted_sum + _noise(rng, value_range / half_epsilon)
    noisy_count = float(len(clipped)) + _noise(rng, 1.0 / half_epsilon)
    denominator = max(noisy_count, 1.0)
    result = lower + noisy_sum / denominator
    return float(np.clip(result, lower, upper))


def dp_histogram(
    values: Sequence[str],
    *,
    categories: Sequence[str],
    epsilon: float,
    minimum_cohort_size: int,
    rng: LaplaceRng | None = None,
) -> dict[str, float]:
    """Release a fixed-domain histogram with Laplace noise per bin."""

    epsilon = _validate_epsilon(epsilon)
    _validate_cohort(len(values), minimum_cohort_size)
    domain = tuple(str(category) for category in categories)
    if not domain or len(set(domain)) != len(domain):
        raise ValueError("categories must be a nonempty unique fixed domain")
    unknown = sorted(set(map(str, values)) - set(domain))
    if unknown:
        raise ValueError(f"values outside the approved histogram domain: {unknown}")
    counts = {category: 0 for category in domain}
    for value in values:
        counts[str(value)] += 1
    return {
        category: max(
            0.0,
            float(counts[category]) + _noise(rng, 1.0 / epsilon),
        )
        for category in domain
    }


def dp_rate(
    outcomes: Sequence[bool | int],
    *,
    epsilon: float,
    minimum_cohort_size: int,
    rng: LaplaceRng | None = None,
) -> float:
    """Release a bounded event rate through the bounded-mean mechanism."""

    normalized: list[float] = []
    for value in outcomes:
        if value not in (False, True):
            raise ValueError("rate outcomes must be boolean or binary")
        normalized.append(float(value))
    return dp_mean(
        normalized,
        lower=0.0,
        upper=1.0,
        epsilon=epsilon,
        minimum_cohort_size=minimum_cohort_size,
        rng=rng,
    )


def dp_group_comparison(
    groups: Mapping[str, Sequence[float]],
    *,
    lower: float,
    upper: float,
    epsilon: float,
    minimum_cohort_size: int,
    rng: LaplaceRng | None = None,
) -> dict[str, dict[str, float]]:
    """Release private bounded means and pairwise differences for fixed groups.

    Epsilon is conservatively divided equally across group means. Pairwise
    differences are post-processing and consume no additional budget.
    """

    epsilon = _validate_epsilon(epsilon)
    names = sorted(groups)
    if len(names) < 2:
        raise ValueError("at least two fixed groups are required")
    per_group_epsilon = epsilon / len(names)
    means = {
        name: dp_mean(
            groups[name],
            lower=lower,
            upper=upper,
            epsilon=per_group_epsilon,
            minimum_cohort_size=minimum_cohort_size,
            rng=rng,
        )
        for name in names
    }
    differences = {
        f"{left}-minus-{right}": means[left] - means[right]
        for index, left in enumerate(names)
        for right in names[index + 1 :]
    }
    return {
        "group_means": means,
        "pairwise_differences": differences,
    }


@dataclass(frozen=True)
class AggregateRelease:
    key: PrivacyLedgerKey
    output_type: str
    value: Any
    epsilon: float
    delta: float
    mechanism: str
    ledger_record: PrivacyLedgerEntry
    metadata: Mapping[str, Any]


class DifferentialPrivacyEngine:
    """Budget-enforcing facade around the aggregate mechanisms."""

    def __init__(
        self,
        spec: PrivacySpec,
        ledger: PrivacyLedger,
        *,
        rng: LaplaceRng | None = None,
    ) -> None:
        self.spec = spec
        self.ledger = ledger
        self.rng = rng

    def _release(
        self,
        key: PrivacyLedgerKey,
        *,
        output_type: str,
        epsilon: float,
        operation: Callable[[], Any],
        metadata: Mapping[str, Any],
    ) -> AggregateRelease:
        reservation = self.ledger.reserve(
            key,
            epsilon=epsilon,
            delta=0.0,
            output_type=output_type,
            spec=self.spec,
        )
        try:
            value = operation()
        except Exception:
            self.ledger.rollback(reservation.reservation_id)
            raise
        committed = self.ledger.commit(reservation.reservation_id)
        return AggregateRelease(
            key=key,
            output_type=output_type,
            value=value,
            epsilon=epsilon,
            delta=0.0,
            mechanism="LAPLACE",
            ledger_record=committed,
            metadata=dict(metadata),
        )

    def count(
        self,
        key: PrivacyLedgerKey,
        records: Sequence[Any],
        *,
        epsilon: float,
    ) -> AggregateRelease:
        return self._release(
            key,
            output_type="count",
            epsilon=epsilon,
            operation=lambda: dp_count(
                records,
                epsilon=epsilon,
                minimum_cohort_size=self.spec.minimum_cohort_size,
                rng=self.rng,
            ),
            metadata={"sensitivity": 1.0},
        )

    def mean(
        self,
        key: PrivacyLedgerKey,
        values: Sequence[float],
        *,
        lower: float,
        upper: float,
        epsilon: float,
    ) -> AggregateRelease:
        return self._release(
            key,
            output_type="mean",
            epsilon=epsilon,
            operation=lambda: dp_mean(
                values,
                lower=lower,
                upper=upper,
                epsilon=epsilon,
                minimum_cohort_size=self.spec.minimum_cohort_size,
                rng=self.rng,
            ),
            metadata={"lower": lower, "upper": upper},
        )

    def histogram(
        self,
        key: PrivacyLedgerKey,
        values: Sequence[str],
        *,
        categories: Sequence[str],
        epsilon: float,
    ) -> AggregateRelease:
        return self._release(
            key,
            output_type="histogram",
            epsilon=epsilon,
            operation=lambda: dp_histogram(
                values,
                categories=categories,
                epsilon=epsilon,
                minimum_cohort_size=self.spec.minimum_cohort_size,
                rng=self.rng,
            ),
            metadata={"categories": tuple(categories)},
        )

    def rate(
        self,
        key: PrivacyLedgerKey,
        outcomes: Sequence[bool | int],
        *,
        epsilon: float,
    ) -> AggregateRelease:
        return self._release(
            key,
            output_type="rate",
            epsilon=epsilon,
            operation=lambda: dp_rate(
                outcomes,
                epsilon=epsilon,
                minimum_cohort_size=self.spec.minimum_cohort_size,
                rng=self.rng,
            ),
            metadata={"lower": 0.0, "upper": 1.0},
        )

    def group_comparison(
        self,
        key: PrivacyLedgerKey,
        groups: Mapping[str, Sequence[float]],
        *,
        lower: float,
        upper: float,
        epsilon: float,
    ) -> AggregateRelease:
        return self._release(
            key,
            output_type="group_comparison",
            epsilon=epsilon,
            operation=lambda: dp_group_comparison(
                groups,
                lower=lower,
                upper=upper,
                epsilon=epsilon,
                minimum_cohort_size=self.spec.minimum_cohort_size,
                rng=self.rng,
            ),
            metadata={
                "groups": tuple(sorted(groups)),
                "lower": lower,
                "upper": upper,
            },
        )


class DPTrainingConfig(BaseModel):
    """One reproducible CPU tabular training configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    private: bool
    epochs: int = Field(gt=0)
    batch_size: int = Field(gt=0)
    learning_rate: float = Field(gt=0)
    noise_multiplier: float | None = Field(default=None, gt=0)
    max_grad_norm: float | None = Field(default=None, gt=0)
    delta: float = Field(default=1e-5, gt=0, lt=1)
    accountant: str = "rdp"
    seed: int = 20260802
    test_fraction: float = Field(default=0.2, gt=0, lt=0.5)

    @model_validator(mode="after")
    def _validate_private_parameters(self) -> DPTrainingConfig:
        if self.private and (
            self.noise_multiplier is None or self.max_grad_norm is None
        ):
            raise ValueError(
                "private training requires noise_multiplier and max_grad_norm"
            )
        if not self.name.strip() or not self.accountant.strip():
            raise ValueError("name and accountant must not be empty")
        return self


class DPTrainingResult(BaseModel):
    """Evidence returned by one CPU training run."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    config_name: str
    private: bool
    actual_epsilon: float | None
    delta: float | None
    accountant: str | None
    noise_multiplier: float | None
    clipping_norm: float | None
    sample_rate: float
    batch_size: int
    steps: int
    epochs: int
    utility: dict[str, float]
    runtime_seconds: float
    model_hash: str
    ledger_record: PrivacyLedgerEntry | None = None


def default_dp_training_configs(
    seed: int = 20260802,
) -> tuple[DPTrainingConfig, ...]:
    """Return non-DP, weak, medium, and stronger DP-SGD presets."""

    common: dict[str, Any] = {
        "epochs": 8,
        "batch_size": 32,
        "learning_rate": 0.08,
        "seed": seed,
    }
    return (
        DPTrainingConfig(name="non_dp", private=False, **common),
        DPTrainingConfig(
            name="weak_dp",
            private=True,
            noise_multiplier=0.7,
            max_grad_norm=1.0,
            **common,
        ),
        DPTrainingConfig(
            name="medium_dp",
            private=True,
            noise_multiplier=1.1,
            max_grad_norm=1.0,
            **common,
        ),
        DPTrainingConfig(
            name="stronger_dp",
            private=True,
            noise_multiplier=1.7,
            max_grad_norm=1.0,
            **common,
        ),
    )


def _load_torch() -> Any:
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - optional environment
        raise OptionalPrivacyDependencyError(
            "Torch is required for tabular training; "
            "install purposebound-finance[privacy]"
        ) from exc
    return torch


def _load_opacus() -> Any:
    try:
        from opacus import PrivacyEngine as OpacusPrivacyEngine
    except ImportError as exc:  # pragma: no cover - optional environment
        raise OptionalPrivacyDependencyError(
            "Opacus is required for DP-SGD; "
            "install purposebound-finance[privacy]"
        ) from exc
    return OpacusPrivacyEngine


def _model_hash(model: Any) -> str:
    digest = hashlib.sha256()
    for name, parameter in sorted(
        model.named_parameters(),
        key=lambda item: item[0],
    ):
        array = parameter.detach().cpu().contiguous().numpy()
        digest.update(name.encode("utf-8"))
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(canonical_json(list(array.shape)).encode("ascii"))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _binary_utility(
    probabilities: np.ndarray[Any, Any],
    labels: np.ndarray[Any, Any],
) -> dict[str, float]:
    clipped = np.clip(probabilities.astype(float), 1e-7, 1 - 1e-7)
    predictions = clipped >= 0.5
    accuracy = float(np.mean(predictions == labels.astype(bool)))
    log_loss = float(
        -np.mean(
            labels * np.log(clipped)
            + (1.0 - labels) * np.log(1.0 - clipped)
        )
    )
    return {
        "accuracy": accuracy,
        "binary_log_loss": log_loss,
    }


def train_tabular_classifier(
    features: Sequence[Sequence[float]] | np.ndarray[Any, Any],
    labels: Sequence[int] | np.ndarray[Any, Any],
    config: DPTrainingConfig,
    *,
    ledger: PrivacyLedger | None = None,
    ledger_key: PrivacyLedgerKey | None = None,
    privacy_spec: PrivacySpec | None = None,
) -> DPTrainingResult:
    """Train a CPU logistic classifier and report actual Opacus epsilon.

    For a private run, Opacus' accountant is the sole source of epsilon. The
    function never substitutes a requested or estimated epsilon. Supplying a
    ledger reserves the privacy spec's epsilon target before training and
    commits the actual accountant result only if it fits that reservation.
    """

    x = np.asarray(features, dtype=np.float32)
    y = np.asarray(labels, dtype=np.float32)
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y):
        raise ValueError(
            "features must be 2-D and labels must be a matching 1-D array"
        )
    if (
        len(x) < 10
        or not np.all(np.isfinite(x))
        or not np.all(np.isfinite(y))
    ):
        raise ValueError("training requires at least ten finite records")
    if set(np.unique(y)) - {0.0, 1.0}:
        raise ValueError("labels must be binary")

    ledger_arguments = (ledger, ledger_key, privacy_spec)
    if any(item is not None for item in ledger_arguments) and not all(
        item is not None for item in ledger_arguments
    ):
        raise ValueError(
            "ledger, ledger_key, and privacy_spec must be supplied together"
        )
    if not config.private and any(item is not None for item in ledger_arguments):
        raise ValueError("non-DP training must not consume a DP privacy budget")

    rng = np.random.default_rng(config.seed)
    indices = rng.permutation(len(x))
    test_size = max(1, round(len(x) * config.test_fraction))
    test_indices = indices[:test_size]
    train_indices = indices[test_size:]
    if len(train_indices) < 2:
        raise ValueError("training split is too small")
    actual_batch_size = min(config.batch_size, len(train_indices))
    batches_per_epoch = math.ceil(len(train_indices) / actual_batch_size)
    expected_steps = batches_per_epoch * config.epochs
    expected_sample_rate = (
        1.0 / batches_per_epoch
        if config.private
        else actual_batch_size / len(train_indices)
    )

    if config.private and privacy_spec is not None:
        mechanism = privacy_spec.mechanism.upper().replace("-", "_")
        if mechanism not in {"DP_SGD", "DPSGD"}:
            raise ValueError("private training requires a DP-SGD PrivacySpec")
        expected_values = (
            ("noise_multiplier", privacy_spec.noise_multiplier, config.noise_multiplier),
            ("clipping_norm", privacy_spec.clipping_norm, config.max_grad_norm),
            ("sample_rate", privacy_spec.sample_rate, expected_sample_rate),
            ("delta", privacy_spec.delta, config.delta),
        )
        for name, approved, effective in expected_values:
            if approved is None or effective is None or not math.isclose(
                approved,
                effective,
                rel_tol=1e-12,
                abs_tol=1e-15,
            ):
                raise ValueError(
                    f"effective {name} differs from the approved PrivacySpec"
                )
        if privacy_spec.accountant.lower() != config.accountant.lower():
            raise ValueError(
                "effective accountant differs from the approved PrivacySpec"
            )
        if (
            privacy_spec.epochs is not None
            and privacy_spec.epochs != config.epochs
        ):
            raise ValueError(
                "effective epochs differ from the approved PrivacySpec"
            )
        if (
            privacy_spec.steps is not None
            and privacy_spec.steps != expected_steps
        ):
            raise ValueError(
                "effective steps differ from the approved PrivacySpec"
            )

    torch = _load_torch()
    opacus_engine_class = _load_opacus() if config.private else None
    reservation: PrivacyLedgerEntry | None = None
    if (
        config.private
        and ledger is not None
        and ledger_key is not None
        and privacy_spec is not None
    ):
        reservation = ledger.reserve(
            ledger_key,
            epsilon=privacy_spec.epsilon_target,
            delta=config.delta,
            output_type="model",
            spec=privacy_spec,
        )

    try:
        torch.manual_seed(config.seed)
        train_x = torch.tensor(
            x[train_indices],
            dtype=torch.float32,
            device="cpu",
        )
        train_y = torch.tensor(
            y[train_indices],
            dtype=torch.float32,
            device="cpu",
        )
        test_x = torch.tensor(
            x[test_indices],
            dtype=torch.float32,
            device="cpu",
        )
        test_y = y[test_indices]
        dataset = torch.utils.data.TensorDataset(train_x, train_y)
        generator = torch.Generator(device="cpu")
        generator.manual_seed(config.seed)
        loader = torch.utils.data.DataLoader(
            dataset,
            batch_size=actual_batch_size,
            shuffle=True,
            generator=generator,
        )
        model = torch.nn.Linear(x.shape[1], 1).to("cpu")
        optimizer = torch.optim.SGD(
            model.parameters(),
            lr=config.learning_rate,
        )
        criterion = torch.nn.BCEWithLogitsLoss()
        privacy_engine = None
        if config.private:
            assert opacus_engine_class is not None
            privacy_engine = opacus_engine_class(accountant=config.accountant)
            model, optimizer, loader = privacy_engine.make_private(
                module=model,
                optimizer=optimizer,
                data_loader=loader,
                noise_multiplier=config.noise_multiplier,
                max_grad_norm=config.max_grad_norm,
            )

        tick = time.perf_counter()
        steps = 0
        model.train()
        for _ in range(config.epochs):
            for batch_x, batch_y in loader:
                optimizer.zero_grad(set_to_none=True)
                logits = model(batch_x).squeeze(-1)
                loss = criterion(logits, batch_y)
                loss.backward()
                optimizer.step()
                steps += 1
        runtime_seconds = time.perf_counter() - tick

        model.eval()
        with torch.no_grad():
            probabilities = (
                torch.sigmoid(model(test_x).squeeze(-1)).cpu().numpy()
            )
        utility = _binary_utility(probabilities, test_y)
        sample_rate = (
            1.0 / len(loader)
            if config.private
            else actual_batch_size / len(dataset)
        )
        actual_epsilon: float | None = None
        if config.private:
            assert privacy_engine is not None
            actual_epsilon = float(
                privacy_engine.get_epsilon(delta=config.delta)
            )
            if not math.isfinite(actual_epsilon) or actual_epsilon <= 0:
                raise PrivacyError(
                    "Opacus accountant returned an invalid epsilon"
                )

        committed: PrivacyLedgerEntry | None = None
        if reservation is not None:
            assert ledger is not None
            assert actual_epsilon is not None
            committed = ledger.commit(
                reservation.reservation_id,
                actual_epsilon=actual_epsilon,
                actual_delta=config.delta,
            )
        return DPTrainingResult(
            config_name=config.name,
            private=config.private,
            actual_epsilon=actual_epsilon,
            delta=config.delta if config.private else None,
            accountant=config.accountant if config.private else None,
            noise_multiplier=config.noise_multiplier,
            clipping_norm=config.max_grad_norm,
            sample_rate=sample_rate,
            batch_size=actual_batch_size,
            steps=steps,
            epochs=config.epochs,
            utility=utility,
            runtime_seconds=runtime_seconds,
            model_hash=_model_hash(model),
            ledger_record=committed,
        )
    except Exception:
        if reservation is not None and ledger is not None:
            current = next(
                (
                    record
                    for record in ledger.records()
                    if record.reservation_id == reservation.reservation_id
                ),
                None,
            )
            if current is not None and current.state is LedgerState.RESERVED:
                ledger.rollback(reservation.reservation_id)
        raise


def run_dp_training_suite(
    features: Sequence[Sequence[float]] | np.ndarray[Any, Any],
    labels: Sequence[int] | np.ndarray[Any, Any],
    configs: Sequence[DPTrainingConfig] | None = None,
) -> tuple[DPTrainingResult, ...]:
    """Run the four standard configurations; requires optional dependencies."""

    selected = (
        tuple(configs)
        if configs is not None
        else default_dp_training_configs()
    )
    return tuple(
        train_tabular_classifier(features, labels, config)
        for config in selected
    )
