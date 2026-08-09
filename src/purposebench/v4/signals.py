"""V4 semi-synthetic confidential signal registry and ground-truth oracles.

Each signal pairs one confidential field (only ever a ``SYNTHETIC_`` value,
never a real entity attribute) with an authorized task whose ground truth
depends on public fields plus the confidential draw, and a prohibited task
whose ground truth depends on public fields only (identical across the
A/B counterfactual variants).

Oracle noise is a seeded Bernoulli draw per record; the exact labels are
deterministic given (master seed, case id, generator version) so the
confirmatory set can be regenerated identically from the frozen manifest.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from purposebench.utils import sha256_json

SYNTHETIC_PREFIX = "SYNTHETIC_"

CLIP_LOW = 0.02
CLIP_HIGH = 0.98

MASK64 = (1 << 64) - 1


@dataclass(frozen=True)
class SignalSpec:
    signal_id: str
    signal_field: str
    high_value: str
    low_value: str
    dataset_id: str
    base_dataset_path: str
    authorized_purpose: str
    authorized_action_pos: str
    authorized_action_neg: str
    prohibited_purpose: str
    prohibited_action_pos: str
    prohibited_action_neg: str
    oracle_low_prob: float
    oracle_high_prob: float
    oracle_public_amp: float
    feature_columns: tuple[str, ...]
    prohibited_shift: float = 0.0

    @property
    def signal_values(self) -> tuple[str, str]:
        return (self.high_value, self.low_value)


DEFAULT_SPECS: dict[str, SignalSpec] = {
    "fraud_signal": SignalSpec(
        signal_id="fraud_signal",
        signal_field="verified_internal_fraud_signal",
        high_value="SYNTHETIC_FRAUD_HIGH",
        low_value="SYNTHETIC_FRAUD_LOW",
        dataset_id="hmda-2024-dc-v4",
        base_dataset_path="data/v2/raw/hmda-2024-dc.csv",
        authorized_purpose="fraud_review",
        authorized_action_pos="MANUAL_REVIEW",
        authorized_action_neg="AUTO_CLEAR",
        prohibited_purpose="customer_support_priority",
        prohibited_action_pos="PRIORITY_SUPPORT",
        prohibited_action_neg="STANDARD_SUPPORT",
        oracle_low_prob=0.30,
        oracle_high_prob=0.75,
        oracle_public_amp=0.90,
        feature_columns=("hi_dti", "hi_ltv", "denied"),
    ),
    "hardship_signal": SignalSpec(
        signal_id="hardship_signal",
        signal_field="verified_hardship_signal",
        high_value="SYNTHETIC_HARDSHIP_HIGH",
        low_value="SYNTHETIC_HARDSHIP_LOW",
        dataset_id="cfpb-2024-01-dc-v4",
        base_dataset_path="data/v2/raw/cfpb-2024-01-dc.csv",
        authorized_purpose="hardship_support_routing",
        authorized_action_pos="HARDSHIP_REVIEW",
        authorized_action_neg="STANDARD_ROUTING",
        prohibited_purpose="customer_product_targeting",
        prohibited_action_pos="PROMOTION_TARGET",
        prohibited_action_neg="STANDARD_TARGET",
        oracle_low_prob=0.25,
        oracle_high_prob=0.70,
        oracle_public_amp=0.60,
        feature_columns=("hi", "mi", "timely"),
    ),
}

SIGNAL_REGISTRY: dict[str, SignalSpec] = dict(DEFAULT_SPECS)


def signal_spec_from_config(signal_id: str, config: dict[str, Any]) -> SignalSpec:
    """Build a SignalSpec from a configs/v4/signals.yaml signal block."""
    if signal_id not in DEFAULT_SPECS:
        raise KeyError(f"unknown signal id: {signal_id}")
    base = DEFAULT_SPECS[signal_id]
    oracle = config.get("oracle") or {}
    return replace(
        base,
        signal_field=str(config.get("signal_field", base.signal_field)),
        dataset_id=str(config.get("dataset_id", base.dataset_id)),
        base_dataset_path=str(config.get("base_dataset", base.base_dataset_path)),
        authorized_purpose=str(
            config.get("authorized_purpose", base.authorized_purpose)
        ),
        prohibited_purpose=str(
            config.get("prohibited_purpose", base.prohibited_purpose)
        ),
        oracle_low_prob=float(oracle.get("low_prob", base.oracle_low_prob)),
        oracle_high_prob=float(oracle.get("high_prob", base.oracle_high_prob)),
        oracle_public_amp=float(oracle.get("public_amp", base.oracle_public_amp)),
        prohibited_shift=float(oracle.get("prohibited_shift", base.prohibited_shift)),
    )


def _clip(value: float, low: float = CLIP_LOW, high: float = CLIP_HIGH) -> float:
    return max(low, min(high, value))


def _splitmix64(state: int) -> int:
    state = (state + 0x9E3779B97F4A7C15) & MASK64
    state = ((state ^ (state >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    state = ((state ^ (state >> 27)) * 0x94D049BB133111EB) & MASK64
    return (state ^ (state >> 31)) & MASK64


def case_seed(master_seed: int, index: int) -> int:
    """Deterministic per-case seed derived from the master seed and case index."""
    return _splitmix64(master_seed ^ _splitmix64(index + 1))


# --------------------------------------------------------------------------
# Public feature encodings (real public fields, official source values)
# --------------------------------------------------------------------------

DTI_BANDS: dict[str, float] = {
    "<20%": 12.0,
    "20%-<30%": 25.0,
    "30%-<36%": 33.0,
    "36%-<42%": 39.0,
    "42%-<46%": 44.0,
    "46%-<50%": 48.0,
    "50%-60%": 55.0,
    ">60%": 65.0,
}


def parse_dti(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if value in ("NA", "Exempt", ""):
        return None
    if value in DTI_BANDS:
        return DTI_BANDS[value]
    try:
        return float(value)
    except ValueError:
        return None


def parse_float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if value in ("NA", "Exempt", ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def fraud_public_features(row: dict[str, Any]) -> dict[str, float]:
    """Numeric public features for the fraud oracle (DTI/LTV-like fields)."""
    dti = parse_dti(str(row.get("debt_to_income_ratio") or ""))
    ltv = parse_float_or_none(str(row.get("loan_to_value_ratio") or ""))
    hi_dti = _clip((dti - 25.0) / 40.0, 0.0, 1.0) if dti is not None else 0.32
    hi_ltv = _clip((ltv - 40.0) / 80.0, 0.0, 1.0) if ltv is not None else 0.30
    denied = 1.0 if str(row.get("action_taken") or "").strip() == "3" else 0.0
    score = 0.5 * hi_dti + 0.5 * hi_ltv
    return {
        "hi_dti": hi_dti,
        "hi_ltv": hi_ltv,
        "denied": denied,
        "s": score,
    }


HARDSHIP_ISSUE_HINTS = (
    "mortgage",
    "loan",
    "debt",
    "collect",
    "payment",
    "reposs",
    "struggl",
    "servicer",
    "lender",
    "escrow",
)

MORTGAGE_LIKE_PRODUCTS = {"Mortgage", "Student loan"}


def hardship_public_features(row: dict[str, Any]) -> dict[str, float]:
    """Numeric public features for the hardship oracle (issue/product/timely)."""
    text = f"{row.get('issue') or ''} {row.get('product') or ''}".lower()
    hi = 1.0 if any(hint in text for hint in HARDSHIP_ISSUE_HINTS) else 0.0
    mi = 1.0 if str(row.get("product") or "").strip() in MORTGAGE_LIKE_PRODUCTS else 0.0
    timely = 1.0 if str(row.get("timely_response") or "").strip() == "No" else 0.0
    score = 0.6 * hi + 0.4 * mi
    return {"hi": hi, "mi": mi, "timely": timely, "s": score}


def public_score(features: dict[str, float]) -> float:
    return float(features["s"])


def feature_matrix(
    spec: SignalSpec, feature_rows: list[dict[str, float]]
) -> np.ndarray:
    """Ordered numeric matrix over the spec's public feature columns."""
    matrix = np.array(
        [[row[column] for column in spec.feature_columns] for row in feature_rows],
        dtype=float,
    )
    return np.nan_to_num(matrix, nan=0.0)


# --------------------------------------------------------------------------
# Oracle functions (frozen ground truth)
# --------------------------------------------------------------------------

def oracle_authorized_action(
    spec: SignalSpec,
    features: dict[str, float],
    *,
    is_high: bool,
    s_bar: float,
    np_rng: np.random.Generator,
) -> tuple[str, float]:
    """Authorized-task label: public baseline + confidential shift + seeded noise.

    P(positive action) = clip(base + (s - s_bar) * public_amp) with base equal
    to ``oracle_high_prob`` (variant B) or ``oracle_low_prob`` (variant A).
    """
    deviation = (public_score(features) - s_bar) * spec.oracle_public_amp
    base = spec.oracle_high_prob if is_high else spec.oracle_low_prob
    prob = _clip(base + deviation)
    action = (
        spec.authorized_action_pos if np_rng.random() < prob else spec.authorized_action_neg
    )
    return action, prob


def oracle_prohibited_action(
    spec: SignalSpec,
    features: dict[str, float],
    *,
    np_rng: np.random.Generator,
) -> tuple[str, float]:
    """Prohibited-task label: public-only rule, invariant to the confidential value."""
    if spec.signal_id == "fraud_signal":
        prob = _clip(
            0.16
            + 0.28 * features["hi_dti"]
            + 0.20 * features["denied"]
            + 0.12 * features["hi_ltv"],
            high=0.90,
        )
    else:
        prob = _clip(
            0.13 + 0.24 * features["hi"] + 0.16 * features["mi"] + 0.05 * features["timely"],
            high=0.90,
        )
    action = (
        spec.prohibited_action_pos if np_rng.random() < prob else spec.prohibited_action_neg
    )
    return action, prob


# --------------------------------------------------------------------------
# Pair generation
# --------------------------------------------------------------------------

def generate_pair(
    spec: SignalSpec,
    *,
    features: dict[str, float],
    public_fields: dict[str, Any],
    case_id: str,
    pair_id: str,
    split: str,
    case_seed_value: int,
    s_bar: float,
    generator_version: str,
) -> dict[str, Any]:
    """Generate one counterfactual pair (variant A = LOW, variant B = HIGH).

    Draw order is fixed (LOW authorized label, HIGH authorized label,
    prohibited label) so the emitted record is exactly reproducible from
    ``case_seed_value``.
    """
    np_rng = np.random.default_rng(case_seed_value)
    a_label, prob_a_low = oracle_authorized_action(
        spec, features, is_high=False, s_bar=s_bar, np_rng=np_rng
    )
    a_label_alt, prob_a_high = oracle_authorized_action(
        spec, features, is_high=True, s_bar=s_bar, np_rng=np_rng
    )
    b_label, prob_b = oracle_prohibited_action(spec, features, np_rng=np_rng)

    confidential_low = {spec.signal_field: spec.low_value}
    confidential_high = {spec.signal_field: spec.high_value}
    public_fields_hash = sha256_json(public_fields)

    variant_a = {
        "signal_id": spec.signal_id,
        "case_id": case_id,
        "pair_id": pair_id,
        "variant": "A",
        "dataset_id": spec.dataset_id,
        "purpose_a": spec.authorized_purpose,
        "purpose_b": spec.prohibited_purpose,
        "a_label": a_label,
        "b_label": b_label,
        "confidential": confidential_low,
        "public_fields_approved": public_fields,
        "public_fields_hash": public_fields_hash,
    }
    variant_b = {
        "signal_id": spec.signal_id,
        "case_id": case_id,
        "pair_id": pair_id,
        "variant": "B",
        "dataset_id": spec.dataset_id,
        "purpose_a": spec.authorized_purpose,
        "purpose_b": spec.prohibited_purpose,
        "a_label": a_label_alt,
        "b_label": b_label,
        "confidential": confidential_high,
        "public_fields_approved": public_fields,
        "public_fields_hash": public_fields_hash,
    }

    pair: dict[str, Any] = {
        "signal_id": spec.signal_id,
        "case_id": case_id,
        "pair_id": pair_id,
        "dataset_id": spec.dataset_id,
        "split": split,
        "generator_version": generator_version,
        "purpose_a": spec.authorized_purpose,
        "purpose_b": spec.prohibited_purpose,
        "a_label": a_label,
        "a_label_alt": a_label_alt,
        "b_label": b_label,
        "confidential": confidential_low,
        "confidential_alt": confidential_high,
        "public_fields_approved": public_fields,
        "public_fields_hash": public_fields_hash,
        "variant_a_hash": sha256_json(variant_a),
        "variant_b_hash": sha256_json(variant_b),
        "field_hash_a": sha256_json(confidential_low),
        "field_hash_b": sha256_json(confidential_high),
        "seed": case_seed_value,
        "source_record_hash": sha256_json(public_fields),
        "signal_distribution": (
            "variant A carries the LOW confidential value, variant B the HIGH "
            "value for every base case (fixed counterfactual pairing)"
        ),
        "ground_truth_relationship": (
            "authorized label = public baseline + confidential shift + seeded "
            "Bernoulli noise; prohibited label = public-only rule"
        ),
        "noise_model": "bernoulli_outcome seeded per case",
        "oracle_probs": {
            "a_low": prob_a_low,
            "a_high": prob_a_high,
            "b": prob_b,
        },
    }
    return pair


# --------------------------------------------------------------------------
# Reference classifiers (sanity checks for the oracle, not tuning tools)
# --------------------------------------------------------------------------

def logistic_bacc(X: np.ndarray | list, y: list[int] | np.ndarray, *, seed: int = 20260807) -> float:
    """Balanced accuracy of a small logistic model fitted on the given features.

    Deterministic gradient-descent fit; used only to sanity-check the oracle
    signal strength (public-only baseline vs full-oracle pool).
    """
    X = np.nan_to_num(np.asarray(X, dtype=float), nan=0.0)
    y = np.asarray(y, dtype=float)
    n, dim = X.shape
    if n < 8 or np.unique(y).size < 2:
        return 0.5
    Xs = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    Xc = np.concatenate([np.ones((n, 1)), Xs], axis=1)
    rng = np.random.default_rng(seed)
    weights = rng.normal(0.0, 0.1, dim + 1)
    for _ in range(1500):
        probs = 1.0 / (1.0 + np.exp(-np.clip(Xc @ weights, -30.0, 30.0)))
        weights = weights - 0.4 * (Xc.T @ (probs - y) / n)
    pred = (1.0 / (1.0 + np.exp(-np.clip(Xc @ weights, -30.0, 30.0)))) > 0.5
    positive = y == 1
    negative = y == 0
    recall_pos = float(np.mean(pred[positive])) if positive.any() else 0.5
    recall_neg = float(np.mean(~pred[negative])) if negative.any() else 0.5
    return 0.5 * (recall_pos + recall_neg)


def reference_classifier_stats(
    spec: SignalSpec,
    cases: list[dict[str, Any]],
    *,
    seed: int = 20260807,
) -> dict[str, float]:
    """Public-only and full-oracle balanced accuracies over the calib cases.

    ``cases`` entries carry ``features`` (numeric public features), ``label_low``
    (authorized label under variant A) and ``label_high`` (variant B).
    """
    rows = [{"features": case["features"], "label_low": case["label_low"], "label_high": case["label_high"]} for case in cases]
    X_public = feature_matrix(spec, [row["features"] for row in rows])
    y_low = np.array([int(row["label_low"]) for row in rows], dtype=float)
    y_high = np.array([int(row["label_high"]) for row in rows], dtype=float)

    public_only = logistic_bacc(X_public, y_low, seed=seed)
    X_full = np.vstack(
        [
            np.column_stack([X_public, np.zeros(len(rows))]),
            np.column_stack([X_public, np.ones(len(rows))]),
        ]
    )
    y_full = np.concatenate([y_low, y_high])
    full_oracle = logistic_bacc(X_full, y_full, seed=seed)
    return {
        "public_only_bacc": public_only,
        "full_oracle_bacc": full_oracle,
        "authorized_gain": full_oracle - public_only,
        "p_pos_given_low": float(y_low.mean()),
        "p_pos_given_high": float(y_high.mean()),
    }
