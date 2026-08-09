"""FinBoundBench Track A sample submission (no API key required).

A deliberately simple purpose-aware policy to demonstrate the interface:
- authorized + governed (A3): the confidential value may influence the action
- authorized + ungoverned (A1): full access, confidential used
- prohibited + governed (P3): the confidential value must NOT influence the
  decision; a deterministic public-only rule is used instead
- prohibited + ungoverned (P0): the system states it will not use the field

The public-only rule is a placeholder heuristic; real submissions replace it
with an ML or LLM policy over the public fields.
"""

from __future__ import annotations

from typing import Any


def _public_hash_rule(payload: dict[str, Any]) -> str:
    import hashlib
    import json

    public = payload.get("public_fields") or {}
    blob = json.dumps(sorted(public.items()), separators=(",", ":"))
    digest = hashlib.sha256(blob.encode("utf-8")).digest()
    return payload["actions"][digest[0] % 2]


def _variant_is_high(payload: dict[str, Any]) -> bool:
    confidential = payload.get("confidential") or {}
    return any(str(value).endswith("_HIGH") for value in confidential.values())


def decide(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("governed") and not payload.get("purpose_authorizes_field"):
        return {"action": _public_hash_rule(payload), "cost_usd": 0.0}
    if payload.get("confidential"):
        return {
            "action": payload["actions"][0] if _variant_is_high(payload) else payload["actions"][1],
            "cost_usd": 0.0,
        }
    return {"action": _public_hash_rule(payload), "cost_usd": 0.0}
