"""Official FFIEC/CFPB HMDA downloader and deterministic v2 transformer."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from purposebench.utils import canonical_json, sha256_file
from purposebench.v2.datasets.augment import (
    PROHIBITED_INTERNAL_FIELDS,
    SYNTHETIC_INTERNAL_DICTIONARY,
    augment_with_synthetic_internal_pairs,
    validate_augmented_pairs,
)
from purposebench.v2.datasets.common import (
    DataFieldDefinition,
    SamplingManifest,
    SourceArtifactManifest,
    StreamingHttpClient,
    TransformationManifest,
    code_bundle_sha256,
    deterministic_sample,
    download_with_optional_client,
    ensure_available,
    ensure_v2_output_path,
    iter_csv_rows,
    normalize_public_value,
    read_source_manifest,
    retrieval_timestamp,
    source_version,
    standard_missing_value_manifest,
    verify_source_artifact,
    write_jsonl,
    write_manifest,
)

HMDA_DATA_BROWSER_CSV_URL = "https://ffiec.cfpb.gov/v2/data-browser-api/view/csv"
HMDA_DATA_PUBLICATION_URL = "https://ffiec.cfpb.gov/data-publication/"
HMDA_TRANSFORMATION_VERSION = "hmda-public-pairs-v2.0.0"

HMDA_LICENSE_USE_NOTES = (
    "Official public HMDA data are used as a protected public research asset, not described as confidential.",
    "The FFIEC/CFPB public files are modified by the Bureau to protect applicant and borrower privacy.",
    "Use must retain source attribution and comply with applicable CFPB/FFIEC website legal notices.",
    "Loan amount and income may contain outliers; public HMDA coverage and reporting rules limit generalization.",
)

HMDA_LIMITATIONS = (
    "HMDA covers reportable mortgage activity and is not a sample of all credit decisions.",
    "The public data are modified for applicant and borrower privacy and contain coded missing or exempt values.",
    "The deterministic sample is a research subset and must not be treated as population-weighted.",
    "All six internal fields are synthetic benchmark constructs with no factual relationship to source records.",
)


class HMDAQuery(BaseModel):
    """A bounded official Data Browser query.

    A state or institution filter is mandatory so this downloader cannot
    accidentally request the entire national multi-gigabyte CSV.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    year: int = Field(ge=2018)
    states: tuple[str, ...] = ()
    leis: tuple[str, ...] = ()
    actions_taken: tuple[int, ...] = ()

    @field_validator("states", mode="before")
    @classmethod
    def _normalize_states(cls, value: Any) -> tuple[str, ...]:
        states = tuple(sorted({str(item).strip().upper() for item in value if str(item).strip()}))
        invalid = [state for state in states if re.fullmatch(r"[A-Z]{2}", state) is None]
        if invalid:
            raise ValueError(f"invalid two-letter state codes: {invalid}")
        return states

    @field_validator("leis", mode="before")
    @classmethod
    def _normalize_leis(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip().upper() for item in value if str(item).strip()}))

    @field_validator("actions_taken", mode="before")
    @classmethod
    def _normalize_actions(cls, value: Any) -> tuple[int, ...]:
        actions = tuple(sorted({int(item) for item in value}))
        if any(action < 1 or action > 8 for action in actions):
            raise ValueError("HMDA action codes must be between 1 and 8")
        return actions

    @model_validator(mode="after")
    def _require_bounded_query(self) -> HMDAQuery:
        if not self.states and not self.leis:
            raise ValueError("HMDA download requires at least one state or LEI filter")
        return self

    def parameters(self) -> dict[str, str]:
        parameters = {"years": str(self.year)}
        if self.states:
            parameters["states"] = ",".join(self.states)
        if self.leis:
            parameters["leis"] = ",".join(self.leis)
        if self.actions_taken:
            parameters["actions_taken"] = ",".join(str(value) for value in self.actions_taken)
        return parameters


HMDA_FIELDS: dict[str, tuple[str, str]] = {
    "activity_year": (
        "string",
        "HMDA activity year.",
    ),
    "lei": (
        "string",
        "Legal Entity Identifier of the reporting institution.",
    ),
    "state_code": (
        "string",
        "Two-letter state code in the public HMDA record.",
    ),
    "county_code": (
        "string",
        "Public HMDA county code.",
    ),
    "census_tract": (
        "string",
        "Public HMDA census tract identifier.",
    ),
    "action_taken": (
        "string",
        "HMDA action-taken code.",
    ),
    "loan_type": (
        "string",
        "HMDA loan-type code.",
    ),
    "loan_purpose": (
        "string",
        "HMDA loan-purpose code.",
    ),
    "loan_amount": (
        "string",
        "Reported public loan amount; retained as source text.",
    ),
    "income": (
        "string",
        "Reported applicant income in the public HMDA representation.",
    ),
    "debt_to_income_ratio": (
        "string",
        "Public HMDA debt-to-income value or category.",
    ),
    "loan_to_value_ratio": (
        "string",
        "Public HMDA loan-to-value value or source code.",
    ),
    "interest_rate": (
        "string",
        "Public HMDA interest-rate value or source code.",
    ),
    "rate_spread": (
        "string",
        "Public HMDA rate-spread value or source code.",
    ),
    "occupancy_type": (
        "string",
        "HMDA occupancy-type code.",
    ),
    "derived_race": (
        "string",
        "Public HMDA derived race category.",
    ),
    "derived_ethnicity": (
        "string",
        "Public HMDA derived ethnicity category.",
    ),
    "derived_sex": (
        "string",
        "Public HMDA derived sex category.",
    ),
    "applicant_age": (
        "string",
        "Public HMDA applicant age category or source code.",
    ),
    "tract_population": (
        "string",
        "Public HMDA census tract population.",
    ),
    "tract_to_msa_income_percentage": (
        "string",
        "Public HMDA tract-to-MSA income percentage.",
    ),
}

HMDA_REQUIRED_FIELDS = {
    "activity_year",
    "lei",
    "state_code",
    "action_taken",
    "loan_amount",
}


def download_hmda(
    query: HMDAQuery,
    *,
    raw_output_path: Path,
    manifest_output_path: Path,
    client: StreamingHttpClient | None = None,
    retrieved_at: datetime | None = None,
    timeout_seconds: float = 600.0,
    overwrite: bool = False,
    max_bytes: int | None = None,
) -> SourceArtifactManifest:
    """Stream a filtered official HMDA CSV and write its source manifest."""

    ensure_available(
        (raw_output_path, manifest_output_path),
        overwrite=overwrite,
    )
    parameters = query.parameters()
    result = download_with_optional_client(
        client=client,
        url=HMDA_DATA_BROWSER_CSV_URL,
        params=parameters,
        output_path=raw_output_path,
        timeout_seconds=timeout_seconds,
        overwrite=overwrite,
        max_bytes=max_bytes,
    )
    timestamp = retrieval_timestamp(retrieved_at)
    manifest = SourceArtifactManifest(
        dataset_id="hmda",
        source_name="FFIEC/CFPB HMDA Data Browser public LAR export",
        official_dataset_page=HMDA_DATA_PUBLICATION_URL,
        source_url=HMDA_DATA_BROWSER_CSV_URL,
        source_parameters=parameters,
        source_version=source_version(
            "hmda-data-browser",
            f"activity-year-{query.year}",
            result.response_headers,
            timestamp,
        ),
        retrieved_at=timestamp,
        response_headers=result.response_headers,
        source_sha256=result.sha256,
        source_bytes=result.bytes_written,
        raw_filename=Path(raw_output_path).name,
        license_use_notes=HMDA_LICENSE_USE_NOTES,
    )
    write_manifest(
        manifest_output_path,
        manifest,
        overwrite=overwrite,
    )
    return manifest


def _public_rows(
    raw_path: Path,
) -> Iterator[dict[str, str | None]]:
    checked_header = False
    selected_fields: tuple[str, ...] = ()
    for source in iter_csv_rows(raw_path):
        if not checked_header:
            available = set(source)
            missing = sorted(HMDA_REQUIRED_FIELDS - available)
            if missing:
                raise ValueError(f"HMDA source is missing required columns: {missing}")
            selected_fields = tuple(field for field in HMDA_FIELDS if field in available)
            checked_header = True
        public = {field: normalize_public_value(source.get(field)) for field in selected_fields}
        public["source_record_id"] = hashlib.sha256(
            canonical_json(public).encode("utf-8")
        ).hexdigest()
        yield public
    if not checked_header:
        raise ValueError("HMDA source contains no data records")


def _data_dictionary(
    approved_fields: tuple[str, ...],
) -> dict[str, DataFieldDefinition]:
    dictionary: dict[str, DataFieldDefinition] = {}
    for field in approved_fields:
        if field == "source_record_id":
            dictionary[field] = DataFieldDefinition(
                data_type="string",
                description=(
                    "Deterministic SHA-256 identifier derived from the selected public fields."
                ),
                origin="official_public_source",
                purpose_classification="approved_public",
                nullable=False,
            )
            continue
        data_type, description = HMDA_FIELDS[field]
        dictionary[field] = DataFieldDefinition(
            data_type=data_type,
            description=description,
            origin="official_public_source",
            purpose_classification="approved_public",
            nullable=True,
        )
    dictionary.update(SYNTHETIC_INTERNAL_DICTIONARY)
    return dictionary


def transform_hmda(
    *,
    raw_path: Path,
    source_manifest_path: Path,
    transformed_output_path: Path,
    manifest_output_path: Path,
    sample_size: int,
    seed: int,
    overwrite: bool = False,
) -> TransformationManifest:
    """Create a deterministic, paired protected-public HMDA research asset."""

    for source_path in (raw_path, source_manifest_path):
        ensure_v2_output_path(source_path)
    ensure_available(
        (transformed_output_path, manifest_output_path),
        overwrite=overwrite,
    )
    source_manifest = read_source_manifest(source_manifest_path)
    verify_source_artifact(
        raw_path,
        source_manifest,
        expected_dataset_id="hmda",
    )
    sampled, scanned = deterministic_sample(
        _public_rows(raw_path),
        dataset_id="hmda",
        sample_size=sample_size,
        seed=seed,
        identity_fields=("source_record_id",),
    )
    if not sampled:
        raise ValueError("HMDA transformation selected no source records")
    paired = augment_with_synthetic_internal_pairs(
        sampled,
        dataset_id="hmda",
        seed=seed,
    )
    output_records = write_jsonl(
        transformed_output_path,
        paired,
        overwrite=overwrite,
    )
    approved_fields = tuple(paired[0]["approved_fields"])
    pair_validation = validate_augmented_pairs(paired)
    code_hash = code_bundle_sha256(
        (
            Path(__file__),
            Path(__file__).with_name("augment.py"),
            Path(__file__).with_name("common.py"),
        )
    )
    manifest = TransformationManifest(
        dataset_id="hmda",
        source_sha256=source_manifest.source_sha256,
        transformation_name=(
            "HMDA public-field selection, stable sampling, and synthetic "
            "internal counterfactual pairing"
        ),
        transformation_version=HMDA_TRANSFORMATION_VERSION,
        transformation_code_sha256=code_hash,
        transformed_sha256=sha256_file(transformed_output_path),
        transformed_filename=Path(transformed_output_path).name,
        base_records=len(sampled),
        pairs=len(sampled),
        output_records=output_records,
        sampling=SamplingManifest(
            method="stable_sha256_bottom_k",
            seed=seed,
            requested_records=sample_size,
            source_records_scanned=scanned,
            identity_fields=("source_record_id",),
            ordering="ascending_sha256_rank",
        ),
        missing_value_treatment=standard_missing_value_manifest(),
        approved_fields=approved_fields,
        prohibited_internal_fields=PROHIBITED_INTERNAL_FIELDS,
        data_dictionary=_data_dictionary(approved_fields),
        pair_validation=pair_validation,
        limitations=HMDA_LIMITATIONS,
    )
    write_manifest(
        manifest_output_path,
        manifest,
        overwrite=overwrite,
    )
    return manifest
