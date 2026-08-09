"""Task payload rendering for the FinBoundBench evaluation harness.

Independent implementation: this module does not import anything from
``src.purposebench``; it re-derives the condition semantics of the frozen
protocol (docs/v4/TASK_DESIGN.md) from the manifest and pair records.

Condition semantics
-------------------
A0  approved_public_only   confidential field stripped by the harness
A1  full_authorized        confidential present, purpose authorizes, ungoverned
A3  psbe_authorized        confidential present, purpose authorizes, governed
P0  full_wrong_purpose     confidential present, purpose prohibits, ungoverned
P2  hardened_prefilter     confidential field stripped by the harness
P3  psbe_prohibited        confidential present, purpose prohibits, governed
ND  identical_repeat       identical authorized payload repeated 3x (floor)
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

CONDITIONS: list[str] = ["A0", "A1", "A3", "P0", "P2", "P3", "ND"]
ND_REPEATS = 3

AUTHORIZED = "authorized"
PROHIBITED = "prohibited"


def load_jsonl(path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_manifest(path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def field_present(condition: str) -> bool:
    return condition not in ("A0", "P2")


def purpose_kind(condition: str) -> str:
    return AUTHORIZED if condition.startswith("A") else PROHIBITED


def is_governed(condition: str) -> bool:
    return condition in ("A3", "P3", "ND")


def render_payload(
    pair: dict[str, Any],
    signal: dict[str, Any],
    condition: str,
    variant: str | None,
    repeat: int | None = None,
) -> dict[str, Any]:
    confidential = pair.get("confidential") or {}
    if variant == "B":
        confidential = pair.get("confidential_alt") or {}

    if condition in ("A0", "P2"):
        confidential = {}

    if purpose_kind(condition) == AUTHORIZED:
        purpose = signal["authorized_purpose"]
        actions = list(signal["authorized_actions"])
        label = pair["a_label"] if variant != "B" else pair.get("a_label_alt", pair["a_label"])
    else:
        purpose = signal["prohibited_purpose"]
        actions = list(signal["prohibited_actions"])
        label = pair["b_label"]

    if condition == "ND":
        purpose = signal["authorized_purpose"]
        actions = list(signal["authorized_actions"])
        label = pair["a_label"]

    request_id = f"{pair['pair_id']}:{condition}:{variant or 'X'}"
    if repeat is not None:
        request_id = f"{pair['pair_id']}:ND:R{repeat}"

    return {
        "request_id": request_id,
        "signal_id": pair["signal_id"],
        "pair_id": pair["pair_id"],
        "case_id": pair["case_id"],
        "dataset_id": pair.get("dataset_id"),
        "purpose": purpose,
        "condition": condition,
        "variant": variant,
        "actions": actions,
        "public_fields": pair.get("public_fields_approved") or {},
        "confidential": confidential,
        "confidential_field": signal["signal_field"],
        "purpose_authorizes_field": purpose_kind(condition) == AUTHORIZED,
        "governed": is_governed(condition),
        "label": label,
    }


def render_split(
    pairs: Iterable[dict[str, Any]],
    signals: dict[str, dict[str, Any]],
    conditions: Iterable[str],
) -> dict[str, dict[str, Any]]:
    requests: dict[str, dict[str, Any]] = {}
    for pair in pairs:
        signal = signals[pair["signal_id"]]
        for condition in conditions:
            if condition == "ND":
                for rep in range(1, ND_REPEATS + 1):
                    payload = render_payload(pair, signal, "ND", "A", repeat=rep)
                    payload["variant"] = "A"
                    requests[payload["request_id"]] = payload
            else:
                for variant in ("A", "B"):
                    payload = render_payload(pair, signal, condition, variant)
                    requests[payload["request_id"]] = payload
    return requests


def payload_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
