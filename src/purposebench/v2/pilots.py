"""Reproducible protocol-v2-local privacy pilot orchestration.

The helpers return serializable evidence and only write to a new, explicitly
namespaced v2 destination. They never mutate protocol-v1 raw streams.
"""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from purposebench.utils import canonical_json
from purposebench.v2.privacy import run_dp_training_suite
from purposebench.v2.privacy_attacks import (
    ConditionAttackInputs,
    evaluate_privacy_attacks,
)


def deterministic_training_data(
    seed: int = 20260802,
) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    """Build the fixed CPU-compatible binary tabular pilot dataset."""

    rng = np.random.default_rng(seed)
    features = rng.normal(size=(512, 8)).astype(np.float32)
    logits = (
        0.9 * features[:, 0]
        - 0.6 * features[:, 1]
        + 0.4 * features[:, 2]
        + rng.normal(scale=0.5, size=512)
    )
    labels = (logits > 0).astype(np.int64)
    return features, labels


def _array_hash(*arrays: np.ndarray[Any, Any]) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        contiguous = np.ascontiguousarray(array)
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(canonical_json(list(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def run_training_pilot(seed: int = 20260802) -> dict[str, Any]:
    """Run non-DP, weak, medium, and stronger DP training on CPU."""

    import opacus
    import torch

    features, labels = deterministic_training_data(seed)
    results = run_dp_training_suite(features, labels)
    return {
        "schemaVersion": "purposebound-finance.dp-training-pilot.v2",
        "recordedAt": datetime.now(UTC).isoformat(),
        "seed": seed,
        "dataset": {
            "kind": "deterministic_synthetic_tabular",
            "records": len(features),
            "features": features.shape[1],
            "positiveLabels": int(labels.sum()),
            "sha256": _array_hash(features, labels),
        },
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "opacus": opacus.__version__,
            "device": "cpu",
        },
        "results": [result.model_dump(mode="json") for result in results],
        "limitations": [
            "This is a local research pilot, not a production model or paper-scale result.",
            "Opacus secure_mode is disabled for reproducible, fast experimentation; a production release must retrain with a cryptographically secure RNG.",
            "Differential privacy applies to the declared adjacency and release process and does not prevent every form of leakage.",
        ],
    }


def _attack_conditions() -> dict[str, ConditionAttackInputs]:
    truth = ["high", "low", "high", "low", "high", "low", "high", "low"]
    common: dict[str, Any] = {
        "sensitive_truth": truth,
        "repeated_query_truth": 10.0,
        "differencing_true_contribution": 1.0,
        "reconstruction_queries": [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ],
        "reconstruction_truth": [1, 0, 1, 0],
    }
    return {
        "ordinary": ConditionAttackInputs(
            utility={"accuracy": 0.873},
            member_losses=[0.11, 0.18, 0.21, 0.29, 0.34, 0.39],
            nonmember_losses=[0.54, 0.61, 0.66, 0.73, 0.79, 0.88],
            sensitive_predictions=[
                "high", "low", "high", "low", "high", "low", "high", "high"
            ],
            repeated_query_answers=[10.0, 10.0, 10.0, 10.0],
            differencing_with_record=51.0,
            differencing_without_record=50.0,
            reconstruction_answers=[1, 0, 1, 0],
            **common,
        ),
        "governed_non_dp": ConditionAttackInputs(
            utility={"accuracy": 0.873},
            member_losses=[0.12, 0.17, 0.22, 0.28, 0.35, 0.40],
            nonmember_losses=[0.53, 0.60, 0.65, 0.72, 0.80, 0.87],
            sensitive_predictions=[
                "high", "low", "high", "low", "high", "low", "high", "high"
            ],
            repeated_query_answers=[10.0, 10.0],
            differencing_with_record=51.0,
            differencing_without_record=50.0,
            reconstruction_answers=[1, 0, 1, 0],
            **common,
        ),
        "governed_dp": ConditionAttackInputs(
            utility={"accuracy": 0.863},
            member_losses=[0.31, 0.42, 0.47, 0.53, 0.58, 0.66],
            nonmember_losses=[0.29, 0.43, 0.49, 0.52, 0.61, 0.67],
            sensitive_predictions=[
                "high", "low", "low", "low", "high", "high", "low", "low"
            ],
            repeated_query_answers=[7.0, 7.0],
            differencing_with_record=49.1,
            differencing_without_record=51.0,
            reconstruction_answers=[0.2, 0.8, 0.3, 0.7],
            **common,
        ),
    }


def run_privacy_attack_pilot(seed: int = 20260802) -> dict[str, Any]:
    """Run the five controlled attacks over the three required conditions."""

    report = evaluate_privacy_attacks(_attack_conditions())
    return {
        "schemaVersion": "purposebound-finance.privacy-attack-pilot.v2",
        "recordedAt": datetime.now(UTC).isoformat(),
        "seed": seed,
        "design": (
            "Deterministic controlled observations validate attack measurement and "
            "comparison plumbing; they are not population estimates."
        ),
        "measurements": [asdict(item) for item in report.measurements],
        "comparisons": [asdict(item) for item in report.comparisons],
        "limitations": list(report.limitations),
    }


def write_new_v2_artifact(
    root: Path,
    relative_path: Path,
    payload: dict[str, Any],
) -> Path:
    """Write a new JSON artifact under results/v2 and reject overwrites."""

    normalized = Path(*relative_path.parts)
    if normalized.is_absolute() or normalized.parts[:2] != ("results", "v2"):
        raise ValueError("privacy pilot output must be a relative results/v2 path")
    destination = (root / normalized).resolve()
    expected_root = (root / "results" / "v2").resolve()
    if expected_root not in destination.parents:
        raise ValueError("privacy pilot output escaped the results/v2 namespace")
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination
