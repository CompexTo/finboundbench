from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from purposebench.v3.transmission import (
    ProjectionClassificationError,
    assert_authorized_projection_covers_approved_fields,
    build_transmission_evidence,
    projection_payload_hash,
)

ROOT = Path(__file__).parents[2]
HMDA_PAIRS = ROOT / "data/v2/generated/hmda-2024-dc-pairs.jsonl"


def _load_pair_variants() -> dict[str, dict[str, dict[str, Any]]]:
    pairs: dict[str, dict[str, dict[str, Any]]] = {}
    for line in HMDA_PAIRS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        pairs.setdefault(row["pair_id"], {})[row["variant"]] = row
    return pairs


def _first_complete_pair() -> tuple[dict[str, Any], dict[str, Any]]:
    pairs = _load_pair_variants()
    for variants in pairs.values():
        if "A" in variants and "B" in variants:
            return variants["A"], variants["B"]
    raise AssertionError("no complete A/B pair available")


def _approved_record(row: dict[str, Any]) -> dict[str, Any]:
    fields = row["fields"]
    return {f: fields[f] for f in row["approved_fields"] if f in fields}


def _prohibited_record(row: dict[str, Any]) -> dict[str, Any]:
    fields = row["fields"]
    return {f: fields[f] for f in row["prohibited_internal_fields"] if f in fields}


def _full_record(row: dict[str, Any]) -> dict[str, Any]:
    return {**_approved_record(row), **_prohibited_record(row)}


def test_b0_evidence_lists_all_permitted_and_prohibited_fields() -> None:
    variant_a, _ = _first_complete_pair()
    approved = sorted(variant_a["approved_fields"])
    prohibited = sorted(variant_a["prohibited_internal_fields"])
    evidence = build_transmission_evidence(
        records=[_full_record(variant_a)],
        selected_fields=approved + prohibited,
        approved_fields=approved,
        prohibited_fields=prohibited,
    )
    assert evidence["transmittedApprovedFields"] == approved
    assert evidence["transmittedProhibitedFields"] == prohibited
    assert evidence["transmittedFields"] == sorted(approved + prohibited)


def test_p3_evidence_lists_exactly_the_approved_projection() -> None:
    variant_a, _ = _first_complete_pair()
    approved = sorted(variant_a["approved_fields"])
    evidence = build_transmission_evidence(
        records=[_approved_record(variant_a)],
        selected_fields=approved,
        approved_fields=approved,
        prohibited_fields=[],
    )
    assert evidence["transmittedFields"] == approved
    assert evidence["transmittedApprovedFields"] == approved
    assert evidence["transmittedProhibitedFields"] == []


def test_payload_hash_changes_when_permitted_payload_changes() -> None:
    variant_a, _ = _first_complete_pair()
    approved = sorted(variant_a["approved_fields"])
    prohibited = sorted(variant_a["prohibited_internal_fields"])
    base = _full_record(variant_a)
    evidence_before = build_transmission_evidence(
        [base], approved + prohibited, approved, prohibited
    )
    mutated = dict(base)
    key = approved[0]
    mutated[key] = "MUTATED_VALUE_FOR_HASH_TEST"
    evidence_after = build_transmission_evidence(
        [mutated], approved + prohibited, approved, prohibited
    )
    assert evidence_before["approvedPayloadHash"] != evidence_after["approvedPayloadHash"]
    assert evidence_before["prohibitedPayloadHash"] == evidence_after["prohibitedPayloadHash"]


def test_pair_members_have_identical_approved_field_hashes() -> None:
    variant_a, variant_b = _first_complete_pair()
    approved = sorted(variant_a["approved_fields"])
    evidence_a = build_transmission_evidence(
        [_approved_record(variant_a)], approved, approved, []
    )
    evidence_b = build_transmission_evidence(
        [_approved_record(variant_b)], approved, approved, []
    )
    assert evidence_a["approvedPayloadHash"] == evidence_b["approvedPayloadHash"]


def test_pair_members_differ_only_in_prohibited_field_hashes() -> None:
    variant_a, variant_b = _first_complete_pair()
    approved = sorted(variant_a["approved_fields"])
    prohibited = sorted(variant_a["prohibited_internal_fields"])
    evidence_a = build_transmission_evidence(
        [_full_record(variant_a)], approved + prohibited, approved, prohibited
    )
    evidence_b = build_transmission_evidence(
        [_full_record(variant_b)], approved + prohibited, approved, prohibited
    )
    assert evidence_a["approvedPayloadHash"] == evidence_b["approvedPayloadHash"]
    assert evidence_a["prohibitedPayloadHash"] != evidence_b["prohibitedPayloadHash"]


def test_projection_hash_matches_platform_payload_shape() -> None:
    variant_a, _ = _first_complete_pair()
    approved = sorted(variant_a["approved_fields"])
    record = _approved_record(variant_a)
    expected = {
        "selectedFields": approved,
        "records": [{f: record.get(f) for f in approved}],
    }
    from purposebench.utils import sha256_json

    assert projection_payload_hash([record], approved) == sha256_json(expected)


def test_authorized_projection_guard_rejects_the_r2_singleton_defect() -> None:
    variant_a, _ = _first_complete_pair()
    approved = variant_a["approved_fields"]
    with pytest.raises(ProjectionClassificationError):
        assert_authorized_projection_covers_approved_fields(
            selected_fields=["source_record_id"], approved_fields=approved
        )
    assert_authorized_projection_covers_approved_fields(
        selected_fields=sorted(approved), approved_fields=approved
    )


def test_classification_must_partition_the_manifest() -> None:
    variant_a, _ = _first_complete_pair()
    approved = sorted(variant_a["approved_fields"])
    with pytest.raises(ProjectionClassificationError):
        build_transmission_evidence(
            [_approved_record(variant_a)],
            selected_fields=approved,
            approved_fields=approved,
            prohibited_fields=["not_in_manifest"],
        )
