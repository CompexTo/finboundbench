"""Protocol v4 — purpose-selective semi-synthetic confidential signals and datasets.

Signal registry, frozen-ground-truth oracle functions and pair generators for
the two v4 purpose-paired signals (fraud_signal on HMDA DC 2024,
hardship_signal on CFPB complaints Jan 2024 DC). Owned by Agent 2 per
CONTRACT_V4.md section 9.
"""

from __future__ import annotations

from purposebench.v4.signals import (
    SIGNAL_REGISTRY,
    SYNTHETIC_PREFIX,
    SignalSpec,
    generate_pair,
    logistic_bacc,
    reference_classifier_stats,
    signal_spec_from_config,
)

__all__ = [
    "SIGNAL_REGISTRY",
    "SYNTHETIC_PREFIX",
    "SignalSpec",
    "generate_pair",
    "logistic_bacc",
    "reference_classifier_stats",
    "signal_spec_from_config",
]

__version__ = "0.1.0"
