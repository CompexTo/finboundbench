from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
import uuid
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx

from purposebench.adapters.base import Adapter
from purposebench.models import BenchmarkCase, ExecutionResult
from purposebench.prompts import build_chat_payload
from purposebench.utils import canonical_json, sha256_json

RESULT_PREFIX = "PURPOSEBENCH_RESULT_JSON="
TERMINAL_EXECUTION_STATES = {"COMPLETED", "FAILED", "BLOCKED", "CANCELLED"}


def _usage_cost(usage: dict[str, Any], model: dict[str, Any]) -> float | None:
    input_rate = model.get("input_cost_per_million")
    output_rate = model.get("output_cost_per_million")
    if input_rate is None or output_rate is None:
        return None
    prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
    completion_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
    return (float(prompt_tokens) * float(input_rate) + float(completion_tokens) * float(output_rate)) / 1_000_000


class CompexAdapter(Adapter):
    """Purpose-bound adapter for the mapped local Compex REST API.

    The adapter uploads the complete synthetic case, asks Compex Analyze to
    create a policy-checked projection, then gives only that Compex artifact to
    a model-agent container executed by Compex. Every required response is
    validated. Missing or contradictory evidence produces an error record.
    """

    def __init__(self) -> None:
        self.mode = os.getenv("COMPEX_MODE", "http").strip().lower()
        self.base_url = os.getenv("COMPEX_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
        self.health_path = os.getenv("COMPEX_HEALTH_PATH", "/health")
        self.api_key = os.getenv("COMPEX_API_KEY", "")
        self.organization_id = os.getenv("COMPEX_ORG_ID", "")
        self.workspace_id = os.getenv("COMPEX_WORKSPACE_ID", "")
        self.agent_image = os.getenv(
            "COMPEX_AGENT_IMAGE", "purposebound-finance-agent:local"
        )
        self.poll_interval = float(os.getenv("COMPEX_POLL_INTERVAL_SECONDS", "1"))
        self.timeout = float(os.getenv("COMPEX_TIMEOUT_SECONDS", "300"))
        self.allow_model_key_persistence = (
            os.getenv("COMPEX_ALLOW_MODEL_KEY_PERSISTENCE", "false").lower() == "true"
        )
        self.trace: list[dict[str, Any]] = []
        self._client: httpx.Client | None = None

    def _workspace_path(self, suffix: str) -> str:
        return (
            f"/organizations/{self.organization_id}/workspaces/"
            f"{self.workspace_id}{suffix}"
        )

    def _validate_configuration(self) -> None:
        if self.mode != "http":
            raise RuntimeError(
                "The mapped Compex integration supports COMPEX_MODE=http only; "
                "no equivalent purpose-bound CLI contract was found"
            )
        missing = [
            name
            for name, value in (
                ("COMPEX_API_KEY", self.api_key),
                ("COMPEX_ORG_ID", self.organization_id),
                ("COMPEX_WORKSPACE_ID", self.workspace_id),
            )
            if not value
        ]
        if missing:
            raise RuntimeError("Missing required Compex configuration: " + ", ".join(missing))
        if not self.api_key.startswith("ck_"):
            raise RuntimeError("COMPEX_API_KEY must be a scoped Compex key beginning with 'ck_'")

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if self._client is None:
            raise RuntimeError("Compex HTTP client is not initialized")
        tick = time.perf_counter()
        try:
            response = self._client.request(method, path, **kwargs)
            latency_ms = round((time.perf_counter() - tick) * 1000, 3)
            response.raise_for_status()
            data = response.json() if response.content else None
            self.trace.append(
                {
                    "method": method,
                    "path": path,
                    "http_status": response.status_code,
                    "status": "ok",
                    "latency_ms": latency_ms,
                    "response": data,
                }
            )
            return data
        except Exception as exc:
            self.trace.append(
                {
                    "method": method,
                    "path": path,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "latency_ms": round((time.perf_counter() - tick) * 1000, 3),
                }
            )
            raise

    @staticmethod
    def _case_csv(case: BenchmarkCase) -> bytes:
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=list(case.all_fields))
        writer.writeheader()
        row: dict[str, Any] = {}
        for key, value in case.all_fields.items():
            row[key] = canonical_json(value) if isinstance(value, (dict, list)) else value
        writer.writerow(row)
        return buffer.getvalue().encode("utf-8")

    @staticmethod
    def _projection_sql(allowed_fields: list[str]) -> str:
        if not allowed_fields:
            raise RuntimeError("Compex condition requires at least one allowed field")
        quoted = [f'"{field.replace(chr(34), chr(34) * 2)}"' for field in allowed_fields]
        return "SELECT " + ", ".join(quoted) + " FROM dataset"

    def _wait_analyze(self, job_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            job = self._request("GET", self._workspace_path(f"/analyze/{job_id}"))
            runs = job.get("runs") or []
            if runs:
                run = runs[0]
                if run.get("status") in TERMINAL_EXECUTION_STATES:
                    return job, run
            if job.get("status") in {"FAILED", "BLOCKED", "CANCELLED"}:
                raise RuntimeError(
                    f"Compex projection job ended as {job.get('status')}: "
                    f"{job.get('blockedReason') or 'no reason supplied'}"
                )
            time.sleep(self.poll_interval)
        raise TimeoutError(f"Timed out waiting for Compex Analyze job {job_id}")

    def _wait_execution(self, run_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            run = self._request("GET", self._workspace_path(f"/executions/{run_id}"))
            if run.get("status") in TERMINAL_EXECUTION_STATES:
                return run
            time.sleep(self.poll_interval)
        raise TimeoutError(f"Timed out waiting for Compex execution {run_id}")

    @staticmethod
    def _extract_agent_result(logs: list[dict[str, Any]]) -> dict[str, Any]:
        matches: list[str] = []
        for line in logs:
            message = str(line.get("message", ""))
            if RESULT_PREFIX in message:
                matches.append(message.split(RESULT_PREFIX, 1)[1])
        if not matches:
            raise RuntimeError("Compex model execution logs did not contain the agent result")
        try:
            result = json.loads(matches[-1])
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Compex agent result is not valid JSON: {exc}") from exc
        if not isinstance(result, dict) or result.get("schema_version") != "1.0":
            raise RuntimeError("Compex agent result schema mismatch")
        return result

    @staticmethod
    def _container_model_url(url: str) -> str:
        parts = urlsplit(url)
        if parts.hostname not in {"127.0.0.1", "localhost"}:
            return url.rstrip("/")
        port = f":{parts.port}" if parts.port else ""
        netloc = f"host.docker.internal{port}"
        return urlunsplit((parts.scheme, netloc, parts.path.rstrip("/"), "", ""))

    def _validate_model_key(self, key: str) -> None:
        placeholders = {"", "local", "ollama", "not-needed", "none"}
        if key.lower() not in placeholders and not self.allow_model_key_persistence:
            raise RuntimeError(
                "Refusing to persist a non-placeholder MODEL_API_KEY in Compex "
                "ExecutionRun.env; secure secret-reference injection is not available"
            )

    def _validate_policy_echo(
        self,
        created: dict[str, Any],
        case: BenchmarkCase,
    ) -> None:
        if created.get("status") != "ACTIVE":
            raise RuntimeError("Compex did not activate the purpose policy")
        field_rules = [r for r in created.get("rules", []) if r.get("ruleType") == "FIELD_ACCESS"]
        if len(field_rules) != 1:
            raise RuntimeError("Compex policy response must contain exactly one FIELD_ACCESS rule")
        expression = field_rules[0].get("expression") or {}
        if sorted(expression.get("allowFields") or []) != sorted(case.allowed_fields):
            raise RuntimeError("Compex policy allowed-field echo does not match the case")
        if sorted(expression.get("denyFields") or []) != sorted(case.forbidden_fields):
            raise RuntimeError("Compex policy denied-field echo does not match the case")

    def execute(
        self,
        case: BenchmarkCase,
        policy: dict[str, Any],
        model: dict[str, Any],
        condition: str,
        seed: int,
    ) -> ExecutionResult:
        started = time.perf_counter()
        self.trace = []
        resources: dict[str, str] = {}
        copied_evidence: dict[str, Any] = {"compex_trace": self.trace, "resources": resources}
        try:
            if condition != "compex_purpose_bound":
                raise RuntimeError("CompexAdapter may only execute compex_purpose_bound")
            self._validate_configuration()
            model_base_url = str(model.get("base_url") or os.getenv("MODEL_BASE_URL", ""))
            model_api_key = str(os.getenv("MODEL_API_KEY", "local"))
            if not model_base_url:
                raise RuntimeError("MODEL_BASE_URL is required for the Compex model agent")
            self._validate_model_key(model_api_key)

            headers = {"Authorization": f"Bearer {self.api_key}"}
            with httpx.Client(base_url=self.base_url, headers=headers, timeout=self.timeout) as client:
                self._client = client
                health = self._request("GET", self.health_path)
                if health.get("status") not in {"ok", "degraded"}:
                    raise RuntimeError(f"Compex health status is {health.get('status')!r}")

                nonce = uuid.uuid4().hex[:12]
                dataset = self._request(
                    "POST",
                    self._workspace_path("/datasets"),
                    json={
                        "name": f"purposebench-{case.case_id}-{nonce}"[:120],
                        "description": canonical_json(
                            {
                                "purpose": case.purpose,
                                "case_id": case.case_id,
                                "pair_id": case.pair_id,
                                "synthetic": True,
                                "allowed_fields": case.allowed_fields,
                            }
                        ),
                        "classification": "INTERNAL",
                    },
                )
                dataset_id = str(dataset.get("id") or "")
                if not dataset_id:
                    raise RuntimeError("Compex dataset creation returned no id")
                resources["dataset_id"] = dataset_id

                csv_bytes = self._case_csv(case)
                csv_sha = hashlib.sha256(csv_bytes).hexdigest()
                version = self._request(
                    "POST",
                    self._workspace_path(f"/datasets/{dataset_id}/versions"),
                    files={"file": (f"{case.case_id}.csv", csv_bytes, "text/csv")},
                    data={"notes": f"purposebench synthetic case {case.case_id}"},
                )
                if version.get("sha256") != csv_sha:
                    raise RuntimeError("Compex uploaded dataset hash does not match local bytes")
                resources["dataset_version_id"] = str(version.get("id") or "")
                schemas = version.get("schemas") or []
                fields = schemas[0].get("fields", []) if schemas else []
                field_by_name = {str(item.get("name")): item for item in fields}
                if set(field_by_name) != set(case.all_fields):
                    raise RuntimeError("Compex inferred field set does not match the synthetic case")
                for field in case.forbidden_fields:
                    field_id = field_by_name[field].get("id")
                    if not field_id:
                        raise RuntimeError(f"Compex returned no field id for {field}")
                    self._request(
                        "PATCH",
                        self._workspace_path(f"/datasets/{dataset_id}/fields/{field_id}"),
                        json={"classification": "RESTRICTED"},
                    )

                policy_body = {
                    "name": f"purposebench-{case.purpose}-{nonce}"[:120],
                    "description": f"Synthetic purpose contract for {case.case_id}",
                    "status": "ACTIVE",
                    "rules": [
                        {
                            "ruleType": "FIELD_ACCESS",
                            "expression": {
                                "purpose": case.purpose,
                                "workflowTypes": ["ANALYZE"],
                                "datasetIds": [dataset_id],
                                "allowFields": case.allowed_fields,
                                "denyFields": case.forbidden_fields,
                            },
                            "order": 0,
                        },
                        {
                            "ruleType": "OUTPUT_CONTROL",
                            "expression": {
                                "purpose": case.purpose,
                                "forbidFields": case.forbidden_fields,
                                "requireStructuredDecision": True,
                            },
                            "order": 1,
                        },
                        {
                            "ruleType": "AUDIT_REQUIRED",
                            "expression": {
                                "purpose": case.purpose,
                                "datasetIds": [dataset_id],
                            },
                            "order": 2,
                        },
                    ],
                }
                created_policy = self._request(
                    "POST", self._workspace_path("/policies"), json=policy_body
                )
                self._validate_policy_echo(created_policy, case)
                policy_id = str(created_policy.get("id") or "")
                if not policy_id:
                    raise RuntimeError("Compex policy creation returned no id")
                resources["policy_id"] = policy_id

                projection = self._request(
                    "POST",
                    self._workspace_path("/analyze"),
                    json={
                        "name": f"purposebench-project-{case.case_id}-{nonce}"[:120],
                        "templateKey": "custom-sql",
                        "datasetId": dataset_id,
                        "datasetVersionId": resources["dataset_version_id"],
                        "policyId": policy_id,
                        "parameters": {"sql": self._projection_sql(case.allowed_fields)},
                    },
                )
                if sorted(projection.get("requestedFields") or []) != sorted(case.allowed_fields):
                    raise RuntimeError("Compex Analyze requestedFields do not match allowed fields")
                projection_job_id = str(projection.get("id") or "")
                approval = projection.get("approvalRequest") or {}
                approval_id = str(projection.get("approvalRequestId") or approval.get("id") or "")
                if not projection_job_id or not approval_id:
                    raise RuntimeError("Compex projection did not return job and approval identifiers")
                resources["projection_job_id"] = projection_job_id
                resources["approval_request_id"] = approval_id

                approved = self._request(
                    "POST",
                    self._workspace_path(f"/approvals/{approval_id}/decisions"),
                    json={
                        "decision": "APPROVED",
                        "comments": f"Synthetic benchmark case {case.case_id}; no production data",
                    },
                )
                if approved.get("status") != "APPROVED":
                    raise RuntimeError("Compex approval did not become APPROVED")

                self._request(
                    "POST", self._workspace_path(f"/analyze/{projection_job_id}/run")
                )
                projection_job, projection_run = self._wait_analyze(projection_job_id)
                if projection_run.get("status") != "COMPLETED":
                    raise RuntimeError(
                        f"Compex projection run ended as {projection_run.get('status')}"
                    )
                resources["projection_run_id"] = str(projection_run.get("id") or "")
                artifacts = projection_run.get("artifacts") or []
                result_artifacts = [
                    item for item in artifacts if str(item.get("storageKey", "")).endswith("result.json")
                ]
                if len(result_artifacts) != 1 or not result_artifacts[0].get("sha256"):
                    raise RuntimeError("Compex projection produced no unique hashed result artifact")
                projection_artifact = result_artifacts[0]

                execution = self._request(
                    "POST",
                    self._workspace_path("/executions"),
                    json={
                        "workflowType": "ANALYZE",
                        "image": self.agent_image,
                        "command": ["python", "/app/agent.py"],
                        "queueName": "analyze",
                        "approvalRequestId": approval_id,
                        "timeoutSec": min(int(self.timeout), 3600),
                        "memoryLimitMb": 512,
                        "networkMode": "bridge",
                        "env": {
                            "__inputs": canonical_json(
                                [
                                    {
                                        "bucket": "compex-artifacts",
                                        "key": projection_artifact["storageKey"],
                                        "mountPath": "/input/projected.json",
                                    }
                                ]
                            ),
                            "MODEL_BASE_URL": self._container_model_url(model_base_url),
                            "MODEL_API_KEY": model_api_key,
                            "MODEL_TIMEOUT_SECONDS": str(
                                model.get(
                                    "timeout_seconds",
                                    os.getenv("MODEL_TIMEOUT_SECONDS", "180"),
                                )
                            ),
                            "PURPOSEBENCH_MODEL": str(model["name"]),
                            "PURPOSEBENCH_TEMPERATURE": str(model.get("temperature", 0.0)),
                            "PURPOSEBENCH_MAX_TOKENS": str(model.get("max_tokens", 500)),
                            "PURPOSEBENCH_REASONING_EFFORT": str(
                                model.get("reasoning_effort", "")
                            ),
                            "PURPOSEBENCH_RESPONSE_FORMAT": (
                                canonical_json(model["response_format"])
                                if "response_format" in model
                                else ""
                            ),
                            "PURPOSEBENCH_SEED": str(seed),
                            "PURPOSEBENCH_TASK": case.user_request,
                            "PURPOSEBENCH_ALLOWED_FIELDS": canonical_json(case.allowed_fields),
                            "PURPOSEBENCH_FORBIDDEN_FIELDS": canonical_json(case.forbidden_fields),
                            "PURPOSEBENCH_SENTINELS": canonical_json(case.sentinel_values),
                            "PURPOSEBENCH_DECISION_LABELS": canonical_json(
                                policy["output_schema"]["decision"]
                            ),
                            "PURPOSEBENCH_CASE_ID": case.case_id,
                        },
                    },
                )
                model_run_id = str(execution.get("id") or "")
                if not model_run_id:
                    raise RuntimeError("Compex model execution returned no run id")
                resources["model_run_id"] = model_run_id
                model_run = self._wait_execution(model_run_id)
                if model_run.get("status") != "COMPLETED":
                    raise RuntimeError(
                        f"Compex model execution ended as {model_run.get('status')}: "
                        f"{model_run.get('error') or 'no error supplied'}"
                    )
                model_artifacts = model_run.get("artifacts") or []
                if not model_artifacts or not all(item.get("sha256") for item in model_artifacts):
                    raise RuntimeError("Compex model execution is missing hashed result artifacts")
                logs = self._request(
                    "GET", self._workspace_path(f"/executions/{model_run_id}/logs")
                )
                agent_result = self._extract_agent_result(logs)

                if sorted(agent_result.get("accessed_fields") or []) != sorted(case.allowed_fields):
                    raise RuntimeError("Agent accessed-field evidence does not match allowed fields")
                if set(agent_result.get("accessed_fields") or []) & set(case.forbidden_fields):
                    raise RuntimeError("Agent evidence reports access to a forbidden field")
                if agent_result.get("requested_model") != model["name"]:
                    raise RuntimeError("Agent did not echo the requested model identifier")
                echoed_seed = agent_result.get("seed")
                if not isinstance(echoed_seed, int) or echoed_seed != seed:
                    raise RuntimeError("Agent did not echo the requested seed")
                actual_model = str(agent_result.get("model_identifier") or "")
                accepted = {str(model["name"]), *map(str, model.get("accepted_identifiers", []))}
                if actual_model not in accepted:
                    raise RuntimeError(
                        f"Model endpoint returned {actual_model!r}; expected one of {sorted(accepted)}"
                    )
                expected_model_request = build_chat_payload(
                    task=case.user_request,
                    visible_data=case.allowed_projection(),
                    condition="compex_purpose_bound",
                    decision_labels=list(policy["output_schema"]["decision"]),
                    policy=None,
                    model=model,
                    seed=seed,
                )
                if agent_result.get("model_request") != expected_model_request:
                    raise RuntimeError(
                        "Compex agent model request differs from the semantically equivalent baseline"
                    )

                bundle = self._request(
                    "POST",
                    self._workspace_path("/evidence"),
                    json={
                        "approvalRequestId": approval_id,
                        "name": f"purposebench-{case.case_id}-{nonce}"[:120],
                        "description": "Synthetic PurposeBound-Finance execution evidence",
                    },
                )
                bundle_id = str(bundle.get("id") or "")
                if (
                    not bundle_id
                    or bundle.get("status") != "READY"
                    or not bundle.get("payload")
                    or not bundle.get("checksum")
                ):
                    raise RuntimeError("Compex returned an incomplete evidence bundle")
                resources["evidence_bundle_id"] = bundle_id
                verification = self._request(
                    "POST", self._workspace_path(f"/evidence/{bundle_id}/verify")
                )
                if verification.get("ok") is not True:
                    raise RuntimeError("Compex evidence checksum verification failed")

                audit_events: list[dict[str, Any]] = []
                for entity_type, entity_id in (
                    ("AnalyzeJob", projection_job_id),
                    ("ExecutionRun", resources["projection_run_id"]),
                    ("ExecutionRun", model_run_id),
                ):
                    events = self._request(
                        "GET",
                        self._workspace_path("/audit"),
                        params={
                            "entityType": entity_type,
                            "entityId": entity_id,
                            "limit": 200,
                        },
                    )
                    audit_events.extend(events or [])

                copied_evidence.update(
                    {
                        "mapping_version": "compex-local-v1",
                        "dataset_upload_sha256": csv_sha,
                        "dataset_input_hash": sha256_json(case.all_fields),
                        "policy": created_policy,
                        "projection_job": projection_job,
                        "projection_run": projection_run,
                        "projection_artifact": projection_artifact,
                        "model_run": model_run,
                        "model_logs": logs,
                        "agent_result": agent_result,
                        "evidence_bundle": bundle,
                        "evidence_verification": verification,
                        "audit_events": audit_events,
                        "output_control_source": "research agent inside Compex execution",
                        "field_access_evidence_semantics": (
                            "explicit policy-checked projection columns; not per-value read telemetry"
                        ),
                    }
                )

                copied_evidence["cleanup"] = {
                    "status": "pending",
                    "policy": (
                        "The harness retires the policy and archives the dataset only after "
                        "this evidence has been appended to immutable raw JSONL"
                    ),
                }

                usage = agent_result.get("token_usage") or {}
                result_status: Literal["ok", "error"] = (
                    "ok" if agent_result.get("status") == "ok" else "error"
                )
                return ExecutionResult(
                    status=result_status,
                    raw_response=str(agent_result.get("raw_output") or ""),
                    parsed_output=agent_result.get("parsed_output") or {},
                    tool_calls=agent_result.get("tool_calls") or [],
                    accessed_fields=agent_result.get("accessed_fields") or [],
                    denied_fields=agent_result.get("denied_fields") or [],
                    policy_events=(
                        agent_result.get("policy_events") or []
                    )
                    + [
                        {
                            "source": "compex_analyze",
                            "type": "field_projection",
                            "status": "allow",
                            "policy_id": policy_id,
                            "requested_fields": projection.get("requestedFields") or [],
                        },
                        {
                            "source": "compex_evidence",
                            "type": "policy_evaluation",
                            "evaluation": (
                                (bundle.get("payload") or {}).get("policies", {}).get("evaluation")
                            ),
                        },
                    ],
                    output_validation_events=agent_result.get("output_validation_events") or [],
                    evidence=copied_evidence,
                    token_usage=usage,
                    estimated_cost=_usage_cost(usage, model),
                    model_version=actual_model,
                    compex_run_id=model_run_id,
                    evidence_id=bundle_id,
                    adapter_latency_ms=round((time.perf_counter() - started) * 1000, 3),
                    attempts=agent_result.get("attempts") or [],
                    error=agent_result.get("error"),
                )
        except Exception as exc:  # noqa: BLE001 - fail closed with partial evidence
            copied_evidence["failure"] = {
                "error_type": type(exc).__name__,
                "error": str(exc),
                "resources_preserved": True,
                "reason": "cleanup is deferred because complete immutable evidence was not copied",
            }
            return ExecutionResult(
                status="error",
                evidence=copied_evidence,
                adapter_latency_ms=round((time.perf_counter() - started) * 1000, 3),
                attempts=self.trace,
                error=str(exc),
            )
        finally:
            self._client = None

    def cleanup(self, evidence: dict[str, Any]) -> list[dict[str, Any]]:
        """Retire synthetic resources after the execution event is durable.

        Dataset deletion in the mapped API is logical archival. Failures are
        returned to the harness and appended to a separate immutable cleanup
        event stream; they never rewrite the execution event.
        """

        resources = evidence.get("resources") or {}
        policy_id = resources.get("policy_id")
        dataset_id = resources.get("dataset_id")
        if not policy_id or not dataset_id or not resources.get("evidence_bundle_id"):
            return [
                {
                    "status": "skipped",
                    "reason": "complete evidence identifiers are not available",
                }
            ]
        events: list[dict[str, Any]] = []
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(base_url=self.base_url, headers=headers, timeout=self.timeout) as client:
            for method, path, body in (
                (
                    "PATCH",
                    self._workspace_path(f"/policies/{policy_id}"),
                    {"status": "RETIRED"},
                ),
                ("DELETE", self._workspace_path(f"/datasets/{dataset_id}"), None),
            ):
                tick = time.perf_counter()
                try:
                    response = client.request(method, path, json=body)
                    response.raise_for_status()
                    events.append(
                        {
                            "method": method,
                            "path": path,
                            "status": "ok",
                            "http_status": response.status_code,
                            "latency_ms": round((time.perf_counter() - tick) * 1000, 3),
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - cleanup is best-effort and audited
                    events.append(
                        {
                            "method": method,
                            "path": path,
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "latency_ms": round((time.perf_counter() - tick) * 1000, 3),
                        }
                    )
        return events
