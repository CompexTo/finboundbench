from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from purposebench.adapters.compex import RESULT_PREFIX, CompexAdapter
from purposebench.dataset.generate import generate_dataset
from purposebench.models import BenchmarkCase
from purposebench.prompts import build_chat_payload
from purposebench.utils import read_jsonl, sha256_json


class FakeCompexState:
    def __init__(self, case: BenchmarkCase, policy: dict[str, Any], model: dict[str, Any]) -> None:
        self.case = case
        self.policy = policy
        self.model = model
        self.upload_sha256 = CompexAdapter._case_csv(case)
        self.upload_body = b""
        self.policy_request: dict[str, Any] = {}
        self.projection_request: dict[str, Any] = {}
        self.execution_request: dict[str, Any] = {}
        self.cleanup_calls: list[tuple[str, str]] = []
        self.return_incomplete_evidence = False

    def agent_result(self) -> dict[str, Any]:
        model_request = build_chat_payload(
            task=self.case.user_request,
            visible_data=self.case.allowed_projection(),
            condition="compex_purpose_bound",
            decision_labels=list(self.policy["output_schema"]["decision"]),
            policy=None,
            model=self.model,
            seed=20260802,
        )
        raw_output = json.dumps(
            {
                "decision": self.case.ground_truth["decision"],
                "risk_score": 50,
                "reasons": [],
            },
            separators=(",", ":"),
        )
        return {
            "schema_version": "1.0",
            "status": "ok",
            "error": None,
            "requested_model": self.model["name"],
            "model_identifier": self.model["name"],
            "seed": 20260802,
            "model_request": model_request,
            "model_request_hash": sha256_json(model_request),
            "model_response": {
                "model": self.model["name"],
                "choices": [{"message": {"content": raw_output}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
            "raw_output": raw_output,
            "parsed_output": json.loads(raw_output),
            "tool_calls": [],
            "accessed_fields": sorted(self.case.allowed_fields),
            "denied_fields": sorted(self.case.forbidden_fields),
            "policy_events": [{"type": "purpose_projection_consumed", "status": "allow"}],
            "output_validation_events": [
                {"type": "structured_output_schema", "status": "pass"},
                {"type": "forbidden_sentinel_scan", "status": "pass"},
            ],
            "token_usage": {"prompt_tokens": 20, "completion_tokens": 10},
            "attempts": [{"attempt": 1, "status": "ok", "http_status": 200}],
            "latency_ms": 10.0,
        }


def _handler(state: FakeCompexState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *args: Any) -> None:
            return

        def _body(self) -> bytes:
            return self.rfile.read(int(self.headers.get("content-length", "0")))

        def _json_body(self) -> dict[str, Any]:
            body = self._body()
            return json.loads(body) if body else {}

        def _send(self, status: int, body: Any) -> None:
            encoded = json.dumps(body).encode("utf-8") if body is not None else b""
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/health":
                self._send(200, {"service": "api", "status": "ok", "version": "0.2.0"})
                return
            if path.endswith("/analyze/projection-job"):
                self._send(
                    200,
                    {
                        "id": "projection-job",
                        "status": "COMPLETED",
                        "requestedFields": state.case.allowed_fields,
                        "runs": [
                            {
                                "id": "projection-run",
                                "status": "COMPLETED",
                                "artifacts": [
                                    {
                                        "storageKey": "workspaces/ws/runs/projection-run/result.json",
                                        "sha256": "a" * 64,
                                        "sizeBytes": 100,
                                    }
                                ],
                            }
                        ],
                    },
                )
                return
            if path.endswith("/executions/model-run"):
                self._send(
                    200,
                    {
                        "id": "model-run",
                        "status": "COMPLETED",
                        "artifacts": [
                            {
                                "storageKey": "workspaces/ws/runs/model-run/result.json",
                                "sha256": "b" * 64,
                                "sizeBytes": 200,
                            }
                        ],
                        "results": [{"name": "run.summary", "value": {"status": "completed"}}],
                    },
                )
                return
            if path.endswith("/executions/model-run/logs"):
                result = json.dumps(state.agent_result(), sort_keys=True, separators=(",", ":"))
                self._send(200, [{"level": "info", "message": RESULT_PREFIX + result}])
                return
            if path.endswith("/audit"):
                self._send(200, [])
                return
            self._send(404, {"message": f"unhandled GET {path}"})

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path.endswith("/datasets"):
                self._json_body()
                self._send(201, {"id": "dataset"})
                return
            if path.endswith("/datasets/dataset/versions"):
                state.upload_body = self._body()
                import hashlib

                self._send(
                    201,
                    {
                        "id": "dataset-version",
                        "sha256": hashlib.sha256(state.upload_sha256).hexdigest(),
                        "schemas": [
                            {
                                "fields": [
                                    {"id": f"field-{index}", "name": name}
                                    for index, name in enumerate(state.case.all_fields)
                                ]
                            }
                        ],
                    },
                )
                return
            if path.endswith("/policies"):
                state.policy_request = self._json_body()
                rules = [dict(rule, id=f"rule-{index}") for index, rule in enumerate(state.policy_request["rules"])]
                self._send(201, {**state.policy_request, "id": "policy", "rules": rules})
                return
            if path.endswith("/analyze"):
                state.projection_request = self._json_body()
                self._send(
                    201,
                    {
                        "id": "projection-job",
                        "status": "SUBMITTED",
                        "requestedFields": state.case.allowed_fields,
                        "approvalRequestId": "approval",
                        "approvalRequest": {"id": "approval", "status": "PENDING"},
                    },
                )
                return
            if path.endswith("/approvals/approval/decisions"):
                request = self._json_body()
                self._send(201, {"id": "approval", "status": request["decision"]})
                return
            if path.endswith("/analyze/projection-job/run"):
                self._send(201, {"id": "projection-job", "status": "QUEUED"})
                return
            if path.endswith("/executions"):
                state.execution_request = self._json_body()
                self._send(201, {"id": "model-run", "status": "QUEUED"})
                return
            if path.endswith("/evidence"):
                request = self._json_body()
                bundle = {
                    "id": "evidence-bundle",
                    "status": "READY",
                    "checksum": "c" * 64,
                    "payload": {
                        "approval": {"id": request["approvalRequestId"], "status": "APPROVED"},
                        "policies": {"evaluation": {"allow": True, "matched": []}},
                        "executions": [{"id": "projection-run"}, {"id": "model-run"}],
                    },
                }
                if state.return_incomplete_evidence:
                    bundle.pop("checksum")
                self._send(201, bundle)
                return
            if path.endswith("/evidence/evidence-bundle/verify"):
                self._send(200, {"bundleId": "evidence-bundle", "ok": True})
                return
            self._send(404, {"message": f"unhandled POST {path}"})

        def do_PATCH(self) -> None:
            path = urlsplit(self.path).path
            body = self._json_body()
            if "/fields/" in path:
                self._send(200, {"classification": body["classification"]})
                return
            if path.endswith("/policies/policy"):
                state.cleanup_calls.append(("PATCH", path))
                self._send(200, {"id": "policy", "status": body["status"]})
                return
            self._send(404, {"message": f"unhandled PATCH {path}"})

        def do_DELETE(self) -> None:
            path = urlsplit(self.path).path
            if path.endswith("/datasets/dataset"):
                state.cleanup_calls.append(("DELETE", path))
                self._send(200, {"id": "dataset", "status": "ARCHIVED"})
                return
            self._send(404, {"message": f"unhandled DELETE {path}"})

    return Handler


@contextmanager
def fake_compex(state: FakeCompexState) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _fixture(tmp_path: Path) -> tuple[BenchmarkCase, dict[str, Any], dict[str, Any]]:
    dataset = tmp_path / "cases.jsonl"
    generate_dataset(dataset, cases_per_workflow=1, seed=20260802)
    case = BenchmarkCase.model_validate(read_jsonl(dataset)[0])
    root = Path(__file__).resolve().parents[1]
    policy = yaml.safe_load((root / "policies" / f"{case.workflow}.yaml").read_text())
    model = {"provider": "local", "name": "qwen3:8b", "temperature": 0.0, "max_tokens": 500}
    return case, policy, model


def _configure(monkeypatch: Any, base_url: str) -> None:
    monkeypatch.setenv("COMPEX_MODE", "http")
    monkeypatch.setenv("COMPEX_BASE_URL", base_url)
    monkeypatch.setenv("COMPEX_API_KEY", "ck_fake_contract_key")
    monkeypatch.setenv("COMPEX_ORG_ID", "org")
    monkeypatch.setenv("COMPEX_WORKSPACE_ID", "ws")
    monkeypatch.setenv("COMPEX_POLL_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.invalid/v1")
    monkeypatch.setenv("MODEL_API_KEY", "local")


def test_compex_contract_and_post_evidence_cleanup(tmp_path: Path, monkeypatch: Any) -> None:
    case, policy, model = _fixture(tmp_path)
    state = FakeCompexState(case, policy, model)
    with fake_compex(state) as base_url:
        _configure(monkeypatch, base_url)
        adapter = CompexAdapter()
        result = adapter.execute(case, policy, model, "compex_purpose_bound", 20260802)

        assert result.status == "ok"
        assert result.compex_run_id == "model-run"
        assert result.evidence_id == "evidence-bundle"
        assert result.accessed_fields == sorted(case.allowed_fields)
        assert result.denied_fields == sorted(case.forbidden_fields)
        assert result.evidence["evidence_verification"]["ok"] is True
        assert state.cleanup_calls == []
        assert all(name.encode() in state.upload_body for name in case.all_fields)
        assert not any(
            field in state.projection_request["parameters"]["sql"]
            for field in case.forbidden_fields
        )
        assert state.execution_request["approvalRequestId"] == "approval"

        cleanup = adapter.cleanup(result.evidence)
        assert [event["status"] for event in cleanup] == ["ok", "ok"]
        assert [method for method, _ in state.cleanup_calls] == ["PATCH", "DELETE"]


def test_compex_contract_fails_closed_on_missing_evidence(tmp_path: Path, monkeypatch: Any) -> None:
    case, policy, model = _fixture(tmp_path)
    state = FakeCompexState(case, policy, model)
    state.return_incomplete_evidence = True
    with fake_compex(state) as base_url:
        _configure(monkeypatch, base_url)
        result = CompexAdapter().execute(
            case, policy, model, "compex_purpose_bound", 20260802
        )

    assert result.status == "error"
    assert "incomplete evidence bundle" in (result.error or "")
    assert result.evidence["failure"]["resources_preserved"] is True
    assert state.cleanup_calls == []
