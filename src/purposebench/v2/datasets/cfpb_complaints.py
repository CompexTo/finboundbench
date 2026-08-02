"""Official CFPB Consumer Complaint downloader and v2 transformer."""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

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
    normalize_public_value,
    read_source_manifest,
    retrieval_timestamp,
    source_version,
    standard_missing_value_manifest,
    verify_source_artifact,
    write_jsonl,
    write_manifest,
)

CFPB_COMPLAINTS_DOWNLOAD_URL = "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"
CFPB_COMPLAINTS_PAGE_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/"
CFPB_COMPLAINTS_FIELD_REFERENCE_URL = "https://cfpb.github.io/api/ccdb/fields.html"
CFPB_TRANSFORMATION_VERSION = "cfpb-complaints-public-pairs-v2.0.0"

CFPB_LICENSE_USE_NOTES = (
    "The CFPB states that published complaint data are freely available to use, analyze, and build on.",
    "This public dataset is handled as a protected public research asset, not described as confidential.",
    "Consumer narratives are published only with consent and after CFPB scrubbing steps, but downstream users should still handle narrative text cautiously.",
    "Use must retain source attribution and comply with applicable CFPB website legal notices.",
)

CFPB_LIMITATIONS = (
    "Published complaints are not a statistical sample and are not necessarily representative of consumer experiences.",
    "Consumer narratives describe reported experiences that CFPB does not adopt or independently verify.",
    "The live bulk file generally changes as complaints are published or updated; the recorded source checksum defines the exact research version.",
    "The deterministic sample is not population-weighted.",
    "All six internal fields are synthetic benchmark constructs with no factual relationship to source records.",
)

CFPB_FIELD_MAP: dict[str, tuple[str, str, str]] = {
    "Complaint ID": (
        "complaint_id",
        "string",
        "CFPB public complaint identifier.",
    ),
    "Date received": (
        "date_received",
        "string",
        "Date the CFPB received the complaint.",
    ),
    "Product": (
        "product",
        "string",
        "Financial product selected for the complaint.",
    ),
    "Sub-product": (
        "sub_product",
        "string",
        "Optional complaint sub-product.",
    ),
    "Issue": (
        "issue",
        "string",
        "Issue selected for the complaint.",
    ),
    "Sub-issue": (
        "sub_issue",
        "string",
        "Optional complaint sub-issue.",
    ),
    "Consumer complaint narrative": (
        "consumer_complaint_narrative",
        "string",
        "Public consumer narrative where publication consent and CFPB scrubbing requirements were met.",
    ),
    "Company public response": (
        "company_public_response",
        "string",
        "Optional public-facing company response.",
    ),
    "Company": (
        "company",
        "string",
        "Company identified in the public complaint record.",
    ),
    "State": (
        "state",
        "string",
        "Published state associated with the complaint.",
    ),
    "ZIP code": (
        "zip_code",
        "string",
        "Published ZIP representation, which may be partial or blank.",
    ),
    "Tags": (
        "tags",
        "string",
        "Published CFPB complaint tags.",
    ),
    "Submitted via": (
        "submitted_via",
        "string",
        "Channel used to submit the complaint.",
    ),
    "Date sent to company": (
        "date_sent_to_company",
        "string",
        "Date the CFPB sent the complaint to the company.",
    ),
    "Company response to consumer": (
        "company_response_to_consumer",
        "string",
        "Categorical company response published by CFPB.",
    ),
    "Timely response?": (
        "timely_response",
        "string",
        "Whether the company response was timely.",
    ),
}

CFPB_REQUIRED_FIELDS = {
    "Complaint ID",
    "Date received",
    "Product",
    "Issue",
    "Company",
}


def download_cfpb_complaints(
    *,
    raw_output_path: Path,
    manifest_output_path: Path,
    client: StreamingHttpClient | None = None,
    retrieved_at: datetime | None = None,
    timeout_seconds: float = 600.0,
    overwrite: bool = False,
    max_bytes: int | None = None,
) -> SourceArtifactManifest:
    """Stream the official CFPB bulk complaint CSV archive."""

    ensure_available(
        (raw_output_path, manifest_output_path),
        overwrite=overwrite,
    )
    result = download_with_optional_client(
        client=client,
        url=CFPB_COMPLAINTS_DOWNLOAD_URL,
        params=None,
        output_path=raw_output_path,
        timeout_seconds=timeout_seconds,
        overwrite=overwrite,
        max_bytes=max_bytes,
    )
    timestamp = retrieval_timestamp(retrieved_at)
    manifest = SourceArtifactManifest(
        dataset_id="cfpb_consumer_complaints",
        source_name="CFPB Consumer Complaint Database bulk CSV",
        official_dataset_page=CFPB_COMPLAINTS_PAGE_URL,
        source_url=CFPB_COMPLAINTS_DOWNLOAD_URL,
        source_parameters={},
        source_version=source_version(
            "cfpb-consumer-complaints",
            "live-bulk-csv",
            result.response_headers,
            timestamp,
        ),
        retrieved_at=timestamp,
        response_headers=result.response_headers,
        source_sha256=result.sha256,
        source_bytes=result.bytes_written,
        raw_filename=Path(raw_output_path).name,
        license_use_notes=CFPB_LICENSE_USE_NOTES,
    )
    write_manifest(
        manifest_output_path,
        manifest,
        overwrite=overwrite,
    )
    return manifest


def _iter_complaint_rows(
    archive_path: Path,
    *,
    max_uncompressed_bytes: int,
) -> Iterator[dict[str, str | None]]:
    with zipfile.ZipFile(archive_path) as archive:
        candidates = [
            item
            for item in archive.infolist()
            if not item.is_dir() and item.filename.lower().endswith(".csv")
        ]
        exact = [
            item for item in candidates if Path(item.filename).name.lower() == "complaints.csv"
        ]
        selected = exact if exact else candidates
        if len(selected) != 1:
            raise ValueError("CFPB archive must contain exactly one complaints CSV")
        member = selected[0]
        if member.file_size > max_uncompressed_bytes:
            raise ValueError("CFPB archive exceeds the approved uncompressed size")
        with (
            archive.open(member, "r") as binary,
            io.TextIOWrapper(
                binary,
                encoding="utf-8-sig",
                newline="",
            ) as text,
        ):
            reader = csv.DictReader(text)
            if reader.fieldnames is None:
                raise ValueError("CFPB complaint CSV has no header")
            missing = sorted(CFPB_REQUIRED_FIELDS - set(reader.fieldnames))
            if missing:
                raise ValueError(f"CFPB source is missing required columns: {missing}")
            selected_fields = tuple(
                source_name for source_name in CFPB_FIELD_MAP if source_name in reader.fieldnames
            )
            for source in reader:
                public = {
                    CFPB_FIELD_MAP[source_name][0]: (
                        normalize_public_value(source.get(source_name))
                    )
                    for source_name in selected_fields
                }
                complaint_id = public.get("complaint_id")
                if complaint_id is None:
                    public["source_record_id"] = hashlib.sha256(
                        canonical_json(public).encode("utf-8")
                    ).hexdigest()
                else:
                    public["source_record_id"] = str(complaint_id)
                yield public


def _data_dictionary(
    approved_fields: tuple[str, ...],
) -> dict[str, DataFieldDefinition]:
    by_output = {
        output_name: (data_type, description)
        for output_name, data_type, description in CFPB_FIELD_MAP.values()
    }
    dictionary: dict[str, DataFieldDefinition] = {}
    for field in approved_fields:
        if field == "source_record_id":
            dictionary[field] = DataFieldDefinition(
                data_type="string",
                description=(
                    "CFPB complaint ID, or a deterministic fallback hash "
                    "if the source identifier is blank."
                ),
                origin="official_public_source",
                purpose_classification="approved_public",
                nullable=False,
            )
            continue
        data_type, description = by_output[field]
        dictionary[field] = DataFieldDefinition(
            data_type=data_type,
            description=description,
            origin="official_public_source",
            purpose_classification="approved_public",
            nullable=True,
        )
    dictionary.update(SYNTHETIC_INTERNAL_DICTIONARY)
    return dictionary


def transform_cfpb_complaints(
    *,
    raw_path: Path,
    source_manifest_path: Path,
    transformed_output_path: Path,
    manifest_output_path: Path,
    sample_size: int,
    seed: int,
    overwrite: bool = False,
    max_uncompressed_bytes: int = 20_000_000_000,
) -> TransformationManifest:
    """Create deterministic paired cases from the official complaint archive."""

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
        expected_dataset_id="cfpb_consumer_complaints",
    )
    sampled, scanned = deterministic_sample(
        _iter_complaint_rows(
            raw_path,
            max_uncompressed_bytes=max_uncompressed_bytes,
        ),
        dataset_id="cfpb_consumer_complaints",
        sample_size=sample_size,
        seed=seed,
        identity_fields=("source_record_id",),
    )
    if not sampled:
        raise ValueError("CFPB complaint transformation selected no source records")
    paired = augment_with_synthetic_internal_pairs(
        sampled,
        dataset_id="cfpb-complaint",
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
        dataset_id="cfpb_consumer_complaints",
        source_sha256=source_manifest.source_sha256,
        transformation_name=(
            "CFPB public-field selection, stable sampling, and synthetic "
            "internal counterfactual pairing"
        ),
        transformation_version=CFPB_TRANSFORMATION_VERSION,
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
        limitations=CFPB_LIMITATIONS,
    )
    write_manifest(
        manifest_output_path,
        manifest,
        overwrite=overwrite,
    )
    return manifest
