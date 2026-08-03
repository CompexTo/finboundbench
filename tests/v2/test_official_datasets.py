from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import TracebackType
from typing import Any, Self

import pytest

from purposebench.utils import canonical_json
from purposebench.v2.datasets import (
    ASSET_CLASSIFICATION,
    CFPB_COMPLAINTS_DOWNLOAD_URL,
    HMDA_DATA_BROWSER_CSV_URL,
    PROHIBITED_INTERNAL_FIELDS,
    HMDAQuery,
    download_cfpb_complaints,
    download_hmda,
    transform_cfpb_complaints,
    transform_hmda,
)
from purposebench.v2.datasets.common import parallel_range_download, stream_download

FIXTURES = Path(__file__).parent / "fixtures"
RETRIEVED_AT = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


class FakeStreamingResponse:
    def __init__(
        self,
        chunks: list[bytes],
        *,
        headers: dict[str, str] | None = None,
        error: Exception | None = None,
        status_code: int = 200,
    ) -> None:
        self._chunks = chunks
        self.headers = headers or {}
        self._error = error
        self.iterations = 0
        self.status_code = status_code

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def raise_for_status(self) -> None:
        if self._error is not None:
            raise self._error

    def iter_bytes(
        self,
        chunk_size: int = 1024 * 1024,
    ) -> Iterator[bytes]:
        assert chunk_size == 1024 * 1024
        for chunk in self._chunks:
            self.iterations += 1
            yield chunk


class FakeStreamingClient:
    def __init__(self, response: FakeStreamingResponse) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def stream(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return self.response


class RangeStreamingClient:
    def __init__(self, body: bytes, etag: str = '"fixture-etag"') -> None:
        self.body = body
        self.etag = etag

    def stream(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> FakeStreamingResponse:
        del method, url, params, timeout
        if not headers or "range" not in headers:
            return FakeStreamingResponse([self.body])
        value = headers["range"].removeprefix("bytes=")
        start_text, end_text = value.split("-", maxsplit=1)
        start = int(start_text)
        end = int(end_text) if end_text else len(self.body) - 1
        selected = self.body[start : end + 1]
        return FakeStreamingResponse(
            _chunks(selected),
            status_code=206,
            headers={
                "ETag": self.etag,
                "Content-Range": f"bytes {start}-{end}/{len(self.body)}",
                "Content-Length": str(len(selected)),
                "Accept-Ranges": "bytes",
            },
        )


def _chunks(data: bytes) -> list[bytes]:
    first = len(data) // 3
    second = first * 2
    return [
        data[:first],
        data[first:second],
        data[second:],
    ]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _complaint_zip() -> bytes:
    source = (FIXTURES / "cfpb_complaints_sample.csv").read_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("complaints.csv", source)
    return buffer.getvalue()


def _assert_pair_invariants(records: list[dict[str, Any]]) -> None:
    pair_ids = {record["pair_id"] for record in records}
    for pair_id in pair_ids:
        pair = sorted(
            (record for record in records if record["pair_id"] == pair_id),
            key=lambda record: record["variant"],
        )
        assert [record["variant"] for record in pair] == ["A", "B"]
        approved = pair[0]["approved_fields"]
        approved_a = {field: pair[0]["fields"][field] for field in approved}
        approved_b = {field: pair[1]["fields"][field] for field in approved}
        assert canonical_json(approved_a) == canonical_json(approved_b)
        changed = {
            field
            for field in pair[0]["fields"]
            if (pair[0]["fields"][field] != pair[1]["fields"][field])
        }
        assert changed == set(PROHIBITED_INTERNAL_FIELDS)
        assert pair[0]["confidential"] is False
        assert pair[0]["asset_classification"] == ASSET_CLASSIFICATION


def test_hmda_download_streams_and_refuses_overwrite(
    tmp_path: Path,
) -> None:
    data = (FIXTURES / "hmda_sample.csv").read_bytes()
    response = FakeStreamingResponse(
        _chunks(data),
        headers={
            "Content-Type": "text/csv",
            "ETag": '"hmda-test-version"',
        },
    )
    client = FakeStreamingClient(response)
    root = tmp_path / "v2" / "hmda"
    raw = root / "source.csv"
    manifest_path = root / "source-manifest.json"
    query = HMDAQuery(
        year=2024,
        states=("md", "DE"),
        actions_taken=(3, 1),
    )

    manifest = download_hmda(
        query,
        raw_output_path=raw,
        manifest_output_path=manifest_path,
        client=client,
        retrieved_at=RETRIEVED_AT,
    )

    assert raw.read_bytes() == data
    assert response.iterations == 3
    assert manifest.source_sha256 == hashlib.sha256(data).hexdigest()
    assert manifest.source_parameters == {
        "years": "2024",
        "states": "DE,MD",
        "actions_taken": "1,3",
    }
    assert manifest.source_url == HMDA_DATA_BROWSER_CSV_URL
    assert manifest.confidential is False
    assert manifest.asset_classification == ASSET_CLASSIFICATION
    assert '"hmda-test-version"' in manifest.source_version
    assert client.calls[0]["url"] == HMDA_DATA_BROWSER_CSV_URL

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        download_hmda(
            query,
            raw_output_path=raw,
            manifest_output_path=manifest_path,
            client=client,
            retrieved_at=RETRIEVED_AT,
        )
    assert len(client.calls) == 1


def test_output_paths_must_be_explicitly_namespaced_v2(
    tmp_path: Path,
) -> None:
    client = FakeStreamingClient(FakeStreamingResponse([b"header\n"]))
    with pytest.raises(ValueError, match="explicit v2"):
        download_hmda(
            HMDAQuery(year=2024, states=("DE",)),
            raw_output_path=tmp_path / "source.csv",
            manifest_output_path=tmp_path / "manifest.json",
            client=client,
            retrieved_at=RETRIEVED_AT,
        )
    assert client.calls == []


def test_hmda_transformation_is_deterministic_and_pair_safe(
    tmp_path: Path,
) -> None:
    data = (FIXTURES / "hmda_sample.csv").read_bytes()
    checksums: list[str] = []
    for directory in ("run-a", "run-b"):
        root = tmp_path / "v2" / directory
        raw = root / "hmda.csv"
        source_manifest = root / "hmda-source.json"
        download_hmda(
            HMDAQuery(year=2024, states=("DE", "MD", "DC")),
            raw_output_path=raw,
            manifest_output_path=source_manifest,
            client=FakeStreamingClient(
                FakeStreamingResponse(
                    _chunks(data),
                    headers={"Last-Modified": "Sun, 02 Aug 2026 12:00:00 GMT"},
                )
            ),
            retrieved_at=RETRIEVED_AT,
        )
        transformed = root / "hmda-pairs.jsonl"
        transform_manifest = root / "hmda-transform.json"
        manifest = transform_hmda(
            raw_path=raw,
            source_manifest_path=source_manifest,
            transformed_output_path=transformed,
            manifest_output_path=transform_manifest,
            sample_size=10,
            seed=20260802,
        )
        records = _read_jsonl(transformed)
        _assert_pair_invariants(records)
        assert manifest.base_records == 5
        assert manifest.pairs == 5
        assert manifest.output_records == 10
        assert manifest.sampling.source_records_scanned == 5
        assert manifest.missing_value_treatment.blank_strings == ("converted_to_null")
        assert manifest.pair_validation["valid"] is True
        assert all(
            manifest.data_dictionary[field].origin == "synthetic_internal"
            for field in PROHIBITED_INTERNAL_FIELDS
        )
        assert any(record["fields"].get("income") is None for record in records)
        assert any(record["fields"].get("debt_to_income_ratio") == "Exempt" for record in records)
        checksums.append(manifest.transformed_sha256)

        with pytest.raises(FileExistsError):
            transform_hmda(
                raw_path=raw,
                source_manifest_path=source_manifest,
                transformed_output_path=transformed,
                manifest_output_path=transform_manifest,
                sample_size=10,
                seed=20260802,
            )
    assert checksums[0] == checksums[1]


def test_cfpb_download_and_transform_offline_fixture(
    tmp_path: Path,
) -> None:
    archive_bytes = _complaint_zip()
    response = FakeStreamingResponse(
        _chunks(archive_bytes),
        headers={
            "Content-Type": "binary/octet-stream",
            "Last-Modified": "Sun, 02 Aug 2026 12:00:00 GMT",
        },
    )
    client = FakeStreamingClient(response)
    root = tmp_path / "v2" / "cfpb"
    raw = root / "complaints.csv.zip"
    source_manifest_path = root / "source.json"

    source_manifest = download_cfpb_complaints(
        raw_output_path=raw,
        manifest_output_path=source_manifest_path,
        client=client,
        retrieved_at=RETRIEVED_AT,
    )
    assert source_manifest.source_url == CFPB_COMPLAINTS_DOWNLOAD_URL
    assert source_manifest.confidential is False
    assert source_manifest.source_sha256 == hashlib.sha256(archive_bytes).hexdigest()

    transformed = root / "complaint-pairs.jsonl"
    transform_manifest_path = root / "transform.json"
    manifest = transform_cfpb_complaints(
        raw_path=raw,
        source_manifest_path=source_manifest_path,
        transformed_output_path=transformed,
        manifest_output_path=transform_manifest_path,
        sample_size=10,
        seed=42,
    )
    records = _read_jsonl(transformed)
    _assert_pair_invariants(records)
    assert len(records) == 10
    assert manifest.base_records == 5
    assert (
        manifest.data_dictionary["consumer_complaint_narrative"].origin == "official_public_source"
    )
    assert any(record["fields"].get("zip_code") is None for record in records)
    assert any("not a statistical sample" in limitation for limitation in manifest.limitations)


def test_stream_download_resumes_only_after_matching_prefix_suffix_and_etag(
    tmp_path: Path,
) -> None:
    body = bytes(range(256)) * 20_000
    output = tmp_path / "v2" / "resume" / "artifact.bin"
    output.parent.mkdir(parents=True)
    partial = output.with_name(f"{output.name}.part")
    partial.write_bytes(body[:2_500_000])

    result = stream_download(
        RangeStreamingClient(body),
        url="https://official.example/artifact.bin",
        params=None,
        output_path=output,
        timeout_seconds=30,
        resume=True,
    )
    assert output.read_bytes() == body
    assert result.sha256 == hashlib.sha256(body).hexdigest()
    assert result.bytes_written == len(body)
    assert result.response_headers["content-length"] == str(len(body))

    mismatched = output.parent / "mismatched.bin"
    mismatch_partial = mismatched.with_name(f"{mismatched.name}.part")
    mismatch_partial.write_bytes(b"wrong" * 100)
    with pytest.raises(ValueError, match="does not match"):
        stream_download(
            RangeStreamingClient(body),
            url="https://official.example/artifact.bin",
            params=None,
            output_path=mismatched,
            timeout_seconds=30,
            resume=True,
        )
    assert mismatch_partial.is_file()


def test_parallel_range_download_locks_every_segment_to_one_etag(
    tmp_path: Path,
) -> None:
    body = bytes(range(256)) * 20_000
    etag = '"parallel-fixture"'

    class RangeHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            range_header = self.headers.get("Range", "")
            if_range = self.headers.get("If-Range")
            start_text, end_text = range_header.removeprefix("bytes=").split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if if_range is not None and if_range != etag:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)
                return
            selected = body[start : end + 1]
            self.send_response(206)
            self.send_header("ETag", etag)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Last-Modified", "Mon, 03 Aug 2026 22:07:12 GMT")
            self.send_header("Content-Length", str(len(selected)))
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(body)}")
            self.end_headers()
            self.wfile.write(selected)

        def log_message(self, format: str, *args: object) -> None:
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        output = tmp_path / "v2" / "parallel" / "artifact.bin"
        result = parallel_range_download(
            url=f"http://127.0.0.1:{server.server_port}/artifact.bin",
            params=None,
            output_path=output,
            timeout_seconds=30,
            workers=4,
            segment_bytes=1024 * 1024,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert output.read_bytes() == body
    assert result.sha256 == hashlib.sha256(body).hexdigest()
    assert result.bytes_written == len(body)
    assert result.response_headers["etag"] == etag
    assert result.response_headers["content-length"] == str(len(body))
    assert not output.with_name(f"{output.name}.segments").exists()


def test_source_checksum_substitution_fails_closed(
    tmp_path: Path,
) -> None:
    data = (FIXTURES / "hmda_sample.csv").read_bytes()
    root = tmp_path / "v2" / "tamper"
    raw = root / "hmda.csv"
    source_manifest = root / "source.json"
    download_hmda(
        HMDAQuery(year=2024, states=("DE",)),
        raw_output_path=raw,
        manifest_output_path=source_manifest,
        client=FakeStreamingClient(FakeStreamingResponse(_chunks(data))),
        retrieved_at=RETRIEVED_AT,
    )
    raw.write_bytes(data + b"\nTAMPERED")
    with pytest.raises(ValueError, match="checksum"):
        transform_hmda(
            raw_path=raw,
            source_manifest_path=source_manifest,
            transformed_output_path=root / "pairs.jsonl",
            manifest_output_path=root / "transform.json",
            sample_size=2,
            seed=1,
        )
