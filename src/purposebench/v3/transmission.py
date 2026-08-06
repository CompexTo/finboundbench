"""Transmission evidence helpers for the v3 purpose-selective benchmark.

Mirrors the platform adapter's projection-classification evidence
(``services/runner/src/providers/commercial-model-adapter.ts``): the payload
hashes are computed over ``{"records": [...], "selectedFields": [...]}``
canonical JSON so research-side pair audits and platform evidence agree.
"""

from __future__ import annotations

import re
from typing import Any

from purposebench.utils import sha256_json

_FIELD_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,127}$")


class ProjectionClassificationError(ValueError):
    """Raised when a projection classification is not a valid partition."""


def classify_projection(
    selected_fields: list[str],
    approved_fields: list[str],
    prohibited_fields: list[str],
) -> dict[str, list[str]]:
    """Validate that approved + prohibited partition the transmitted manifest."""
    combined = list(approved_fields) + list(prohibited_fields)
    if not combined or len(set(combined)) != len(combined):
        raise ProjectionClassificationError(
            "Projection field classification must be non-empty and unique"
        )
    if sorted(combined) != sorted(selected_fields):
        raise ProjectionClassificationError(
            "Projection field classification must partition the transmitted field manifest"
        )
    for field in combined:
        if not _FIELD_PATTERN.match(field) or "*" in field:
            raise ProjectionClassificationError(
                "Projection field classification contains an unsafe field"
            )
    return {
        "approvedFields": sorted(approved_fields),
        "prohibitedFields": sorted(prohibited_fields),
    }


def projection_payload_hash(
    records: list[dict[str, Any]], fields: list[str]
) -> str:
    """Hash the projection of ``records`` onto ``fields`` only."""
    ordered = sorted(fields)
    material = {
        "selectedFields": ordered,
        "records": [
            {field: record.get(field) for field in ordered} for record in records
        ],
    }
    return sha256_json(material)


def build_transmission_evidence(
    records: list[dict[str, Any]],
    selected_fields: list[str],
    approved_fields: list[str],
    prohibited_fields: list[str],
) -> dict[str, Any]:
    """Build the transmitted-field evidence block for one execution.

    Fails closed when the classification does not partition the transmitted
    manifest or when a record's keys differ from the manifest.
    """
    if not records:
        raise ProjectionClassificationError("Approved projection contains no records")
    classification = classify_projection(
        selected_fields, approved_fields, prohibited_fields
    )
    expected = sorted(selected_fields)
    for record in records:
        if sorted(record.keys()) != expected:
            raise ProjectionClassificationError(
                "Record fields differ from the approved transmitted field manifest"
            )
    return {
        "transmittedFields": sorted(selected_fields),
        "transmittedApprovedFields": classification["approvedFields"],
        "transmittedProhibitedFields": classification["prohibitedFields"],
        "approvedPayloadHash": projection_payload_hash(
            records, classification["approvedFields"]
        ),
        "prohibitedPayloadHash": projection_payload_hash(
            records, classification["prohibitedFields"]
        ),
    }


def assert_authorized_projection_covers_approved_fields(
    selected_fields: list[str], approved_fields: list[str]
) -> None:
    """Guard against the R2 reduced-run defect.

    An authorized-purpose condition must transmit every purpose-approved
    field; a projection that drops approved fields makes task utility and
    purpose selectivity unmeasurable (see docs/v3/TRANSMITTED_FIELD_AUDIT.md).
    """
    missing = [field for field in approved_fields if field not in selected_fields]
    if missing:
        raise ProjectionClassificationError(
            "Authorized condition projection omits approved fields: "
            + ", ".join(sorted(missing))
        )
