"""Reference degenerate strategies and the oracle baseline.

These are the anti-gaming suite baselines described in the competition
proposal: always-refuse, always-same, always-use-full, ignore-confidential,
random, purpose-agnostic, oracle. Each strategy is a pure function of the
rendered payload, so the suite runs with no API key and no network.

The oracle baseline reads ``payload["_ground_truth"]``, which the harness
injects only for the oracle run on development data (labels are public in
the development split; the oracle never appears in final rankings).
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from typing import Any

Strategy = Callable[[dict[str, Any]], dict[str, Any]]


def always_refuse(payload: dict[str, Any]) -> dict[str, Any]:
    return {"action": payload["actions"][0], "cost_usd": 0.0}


def always_same(payload: dict[str, Any]) -> dict[str, Any]:
    return {"action": payload["actions"][1], "cost_usd": 0.0}


def _variant_is_high(payload: dict[str, Any]) -> bool:
    confidential = payload.get("confidential") or {}
    return any(str(value).endswith("_HIGH") for value in confidential.values())


def always_use_full(payload: dict[str, Any]) -> dict[str, Any]:
    return {"action": payload["actions"][0] if _variant_is_high(payload) else payload["actions"][1], "cost_usd": 0.0}


def _public_hash_rule(payload: dict[str, Any]) -> str:
    public = payload.get("public_fields") or {}
    blob = json.dumps(sorted(public.items()), separators=(",", ":"))
    digest = hashlib.sha256(blob.encode("utf-8")).digest()
    return payload["actions"][digest[0] % 2]


def ignore_confidential(payload: dict[str, Any]) -> dict[str, Any]:
    return {"action": _public_hash_rule(payload), "cost_usd": 0.0}


def random_strategy(payload: dict[str, Any]) -> dict[str, Any]:
    rng = random.Random(hashlib.sha256(payload["request_id"].encode("utf-8")).hexdigest())
    return {"action": rng.choice(payload["actions"]), "cost_usd": 0.0}


def purpose_agnostic(payload: dict[str, Any]) -> dict[str, Any]:
    return {"action": payload["actions"][0] if _variant_is_high(payload) else payload["actions"][1], "cost_usd": 0.0}


def oracle(payload: dict[str, Any]) -> dict[str, Any]:
    ground_truth = payload.get("_ground_truth")
    if ground_truth in payload["actions"]:
        return {"action": ground_truth, "cost_usd": 0.0}
    return {"action": payload["actions"][0], "cost_usd": 0.0}


BASELINES: dict[str, Strategy] = {
    "always-refuse": always_refuse,
    "always-same": always_same,
    "always-use-full": always_use_full,
    "ignore-confidential": ignore_confidential,
    "random": random_strategy,
    "purpose-agnostic": purpose_agnostic,
    "oracle": oracle,
}
