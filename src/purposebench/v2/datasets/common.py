"""Shared streaming, provenance, and deterministic transformation utilities."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections.abc import Iterable, Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Protocol, Self, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field

from purposebench.utils import canonical_json, sha256_file

ASSET_CLASSIFICATION: Literal["PROTECTED_PUBLIC_RESEARCH_ASSET"] = "PROTECTED_PUBLIC_RESEARCH_ASSET"
SOURCE_MANIFEST_SCHEMA: Literal["compex-public-source-v2"] = "compex-public-source-v2"
TRANSFORMATION_MANIFEST_SCHEMA: Literal["compex-public-transformation-v2"] = (
    "compex-public-transformation-v2"
)


class DataFieldDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    data_type: str
    description: str
    origin: Literal["official_public_source", "synthetic_internal"]
    purpose_classification: Literal["approved_public", "prohibited_internal"]
    nullable: bool = True


class SourceArtifactManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["compex-public-source-v2"] = SOURCE_MANIFEST_SCHEMA
    dataset_id: str
    asset_classification: Literal["PROTECTED_PUBLIC_RESEARCH_ASSET"] = ASSET_CLASSIFICATION
    confidential: Literal[False] = False
    source_name: str
    official_dataset_page: str
    source_url: str
    source_parameters: dict[str, str] = Field(default_factory=dict)
    source_version: str
    retrieved_at: str
    response_headers: dict[str, str] = Field(default_factory=dict)
    source_sha256: str
    source_bytes: int = Field(ge=0)
    raw_filename: str
    license_use_notes: tuple[str, ...]


class SamplingManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["stable_sha256_bottom_k"]
    seed: int
    requested_records: int = Field(gt=0)
    source_records_scanned: int = Field(ge=0)
    identity_fields: tuple[str, ...]
    ordering: Literal["ascending_sha256_rank"]


class MissingValueManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    blank_strings: Literal["converted_to_null"]
    whitespace: Literal["trimmed"]
    source_codes: Literal["preserved"]
    row_policy: Literal["records_with_missing_values_retained"]


class TransformationManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["compex-public-transformation-v2"] = TRANSFORMATION_MANIFEST_SCHEMA
    dataset_id: str
    asset_classification: Literal["PROTECTED_PUBLIC_RESEARCH_ASSET"] = ASSET_CLASSIFICATION
    confidential: Literal[False] = False
    source_sha256: str
    transformation_name: str
    transformation_version: str
    transformation_code_sha256: str
    transformed_sha256: str
    transformed_filename: str
    base_records: int = Field(ge=0)
    pairs: int = Field(ge=0)
    output_records: int = Field(ge=0)
    sampling: SamplingManifest
    missing_value_treatment: MissingValueManifest
    approved_fields: tuple[str, ...]
    prohibited_internal_fields: tuple[str, ...]
    data_dictionary: dict[str, DataFieldDefinition]
    pair_validation: dict[str, bool | int]
    limitations: tuple[str, ...]


class StreamingResponse(Protocol):
    @property
    def headers(self) -> Mapping[str, str]: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def raise_for_status(self) -> None: ...

    def iter_bytes(self, chunk_size: int = ...) -> Iterator[bytes]: ...


class StreamingHttpClient(Protocol):
    def stream(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> StreamingResponse: ...


class DownloadResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sha256: str
    bytes_written: int
    response_headers: dict[str, str]


def ensure_v2_output_path(path: Path) -> Path:
    """Require an explicit v2 namespace to protect frozen v1 artifacts."""

    resolved = path.expanduser().resolve()
    if "v2" not in {part.lower() for part in resolved.parts}:
        raise ValueError(f"output path must contain an explicit v2 directory segment: {path}")
    return resolved


def ensure_distinct_v2_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    """Resolve v2 artifact paths and reject source/output aliasing."""

    resolved = tuple(ensure_v2_output_path(path) for path in paths)
    if len(set(resolved)) != len(resolved):
        raise ValueError("source and output artifact paths must be distinct")
    return resolved


def _part_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.part")


def ensure_available(paths: Sequence[Path], *, overwrite: bool) -> None:
    for path in ensure_distinct_v2_paths(paths):
        if os.path.lexists(path) and not overwrite:
            raise FileExistsError(f"refusing to overwrite preservation-sensitive artifact: {path}")
        temporary = _part_path(path)
        if os.path.lexists(temporary) and not overwrite:
            raise FileExistsError(f"stale partial artifact exists: {temporary}")


def _publish_temporary(
    temporary: Path,
    output: Path,
    *,
    overwrite: bool,
) -> None:
    if overwrite:
        os.replace(temporary, output)
        return
    try:
        # A same-directory hard link is an atomic create-if-absent operation.
        # It avoids the cross-platform clobber semantics of replace/rename.
        os.link(temporary, output)
    except FileExistsError as exc:
        raise FileExistsError(
            f"refusing to overwrite preservation-sensitive artifact: {output}"
        ) from exc
    temporary.unlink()


def atomic_write_text(
    path: Path,
    text: str,
    *,
    overwrite: bool = False,
) -> None:
    output = ensure_v2_output_path(path)
    ensure_available((output,), overwrite=overwrite)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = _part_path(output)
    if os.path.lexists(temporary):
        if not overwrite:
            raise FileExistsError(f"stale partial artifact exists: {temporary}")
        temporary.unlink()
    try:
        mode = "w" if overwrite else "x"
        with temporary.open(mode, encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        _publish_temporary(temporary, output, overwrite=overwrite)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def write_manifest(
    path: Path,
    manifest: BaseModel,
    *,
    overwrite: bool = False,
) -> None:
    body = canonical_json(manifest.model_dump(mode="json")) + "\n"
    atomic_write_text(path, body, overwrite=overwrite)


def read_source_manifest(path: Path) -> SourceArtifactManifest:
    with path.open("r", encoding="utf-8") as handle:
        return SourceArtifactManifest.model_validate(json.load(handle))


def stream_download(
    client: StreamingHttpClient,
    *,
    url: str,
    params: Mapping[str, str] | None,
    output_path: Path,
    timeout_seconds: float,
    overwrite: bool = False,
    max_bytes: int | None = None,
) -> DownloadResult:
    """Stream a response to an atomic local artifact while hashing its bytes."""

    output = ensure_v2_output_path(output_path)
    ensure_available((output,), overwrite=overwrite)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = _part_path(output)
    if os.path.lexists(temporary):
        if not overwrite:
            raise FileExistsError(f"stale partial artifact exists: {temporary}")
        temporary.unlink()

    digest = hashlib.sha256()
    bytes_written = 0
    response_headers: dict[str, str] = {}
    try:
        with client.stream(
            "GET",
            url,
            params=params,
            timeout=timeout_seconds,
        ) as response:
            response.raise_for_status()
            response_headers = {
                key.lower(): str(value)
                for key, value in response.headers.items()
                if key.lower()
                in {
                    "content-type",
                    "content-length",
                    "content-disposition",
                    "etag",
                    "last-modified",
                }
            }
            mode = "wb" if overwrite else "xb"
            with temporary.open(mode) as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    bytes_written += len(chunk)
                    if max_bytes is not None and bytes_written > max_bytes:
                        raise ValueError(f"download exceeded max_bytes={max_bytes}")
                    digest.update(chunk)
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        _publish_temporary(temporary, output, overwrite=overwrite)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return DownloadResult(
        sha256=digest.hexdigest(),
        bytes_written=bytes_written,
        response_headers=response_headers,
    )


def download_with_optional_client(
    *,
    client: StreamingHttpClient | None,
    url: str,
    params: Mapping[str, str] | None,
    output_path: Path,
    timeout_seconds: float,
    overwrite: bool,
    max_bytes: int | None,
) -> DownloadResult:
    if client is not None:
        return stream_download(
            client,
            url=url,
            params=params,
            output_path=output_path,
            timeout_seconds=timeout_seconds,
            overwrite=overwrite,
            max_bytes=max_bytes,
        )
    with httpx.Client(follow_redirects=True) as owned_client:
        return stream_download(
            cast(StreamingHttpClient, owned_client),
            url=url,
            params=params,
            output_path=output_path,
            timeout_seconds=timeout_seconds,
            overwrite=overwrite,
            max_bytes=max_bytes,
        )


def retrieval_timestamp(value: datetime | None = None) -> str:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("retrieval timestamp must be timezone-aware")
    return timestamp.astimezone(UTC).isoformat()


def source_version(
    dataset_prefix: str,
    declared_version: str,
    headers: Mapping[str, str],
    retrieved_at: str,
) -> str:
    server_version = (
        headers.get("etag") or headers.get("last-modified") or f"retrieved-{retrieved_at}"
    )
    return f"{dataset_prefix}:{declared_version}:{server_version}"


def normalize_public_value(value: str | None) -> str | None:
    """Trim source text and convert blanks to null; preserve coded values."""

    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def iter_csv_rows(
    path: Path,
    *,
    encoding: str = "utf-8-sig",
) -> Iterator[dict[str, str | None]]:
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        for row in reader:
            yield {str(key): value for key, value in row.items() if key is not None}


def deterministic_sample(
    rows: Iterable[Mapping[str, str | None]],
    *,
    dataset_id: str,
    sample_size: int,
    seed: int,
    identity_fields: Sequence[str],
) -> tuple[list[dict[str, str | None]], int]:
    """Select bottom-k SHA-256-ranked rows with bounded memory."""

    if sample_size < 1:
        raise ValueError("sample_size must be at least one")
    selected: list[tuple[str, str, dict[str, str | None]]] = []
    scanned = 0
    for source_row in rows:
        row = dict(source_row)
        scanned += 1
        identity = "|".join(str(row.get(field) or "") for field in identity_fields)
        canonical_row = canonical_json(row)
        rank_material = f"{dataset_id}|{seed}|{identity}|{canonical_row}"
        rank = hashlib.sha256(rank_material.encode("utf-8")).hexdigest()
        selected.append((rank, canonical_row, row))
        if len(selected) >= sample_size * 2:
            selected.sort(key=lambda item: (item[0], item[1]))
            del selected[sample_size:]
    selected.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in selected[:sample_size]], scanned


def write_jsonl(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    *,
    overwrite: bool = False,
) -> int:
    materialized = list(rows)
    text = "".join(canonical_json(dict(row)) + "\n" for row in materialized)
    atomic_write_text(path, text, overwrite=overwrite)
    return len(materialized)


def verify_source_artifact(
    raw_path: Path,
    manifest: SourceArtifactManifest,
    *,
    expected_dataset_id: str,
) -> None:
    if manifest.dataset_id != expected_dataset_id:
        raise ValueError(
            f"source manifest dataset is {manifest.dataset_id}, expected {expected_dataset_id}"
        )
    actual = sha256_file(raw_path)
    if actual != manifest.source_sha256:
        raise ValueError("raw source checksum does not match its source manifest")


def standard_missing_value_manifest() -> MissingValueManifest:
    return MissingValueManifest(
        blank_strings="converted_to_null",
        whitespace="trimmed",
        source_codes="preserved",
        row_policy="records_with_missing_values_retained",
    )


def code_bundle_sha256(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        (item.resolve() for item in paths),
        key=lambda item: item.name,
    ):
        digest.update(path.name.encode("utf-8"))
        digest.update(sha256_file(path).encode("ascii"))
    return digest.hexdigest()
