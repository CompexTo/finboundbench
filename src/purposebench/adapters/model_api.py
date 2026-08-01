from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from purposebench.adapters.base import Adapter
from purposebench.models import BenchmarkCase, ExecutionResult
from purposebench.prompts import build_chat_payload, validate_structured_output


def _usage_cost(usage: dict[str, Any], model: dict[str, Any]) -> float | None:
    input_rate = model.get("input_cost_per_million")
    output_rate = model.get("output_cost_per_million")
    if input_rate is None or output_rate is None:
        return None
    prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
    completion_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
    return (float(prompt_tokens) * float(input_rate) + float(completion_tokens) * float(output_rate)) / 1_000_000


def _guard_output(text: str, case: BenchmarkCase, policy: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    filtered = text
    redactions: list[dict[str, Any]] = []
    candidates: list[tuple[str, str]] = []
    for field in policy["forbidden_fields"]:
        candidates.append(("field_name", str(field)))
        if field in case.all_fields:
            value = case.all_fields[field]
            if isinstance(value, (str, int, float, bool)):
                candidates.append(("field_value", str(value)))
    candidates.extend(("sentinel", value) for value in case.sentinel_values)
    for kind, value in sorted(set(candidates), key=lambda item: len(item[1]), reverse=True):
        if value and value in filtered:
            occurrences = filtered.count(value)
            filtered = filtered.replace(value, f"[BLOCKED_{kind.upper()}]")
            redactions.append({"type": kind, "value_hash_only": True, "occurrences": occurrences})
    return filtered, redactions


class OpenAICompatibleAdapter(Adapter):
    def __init__(self) -> None:
        self.base_url = os.getenv("MODEL_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
        self.api_key = os.getenv("MODEL_API_KEY", "local")
        self.timeout = float(os.getenv("MODEL_TIMEOUT_SECONDS", "180"))

    def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        self.last_attempts: list[dict[str, Any]] = []
        for attempt in range(3):
            started = time.perf_counter()
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
                    response.raise_for_status()
                    self.last_attempts.append(
                        {
                            "attempt": attempt + 1,
                            "status": "ok",
                            "http_status": response.status_code,
                            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                        }
                    )
                    return response.json()
            except Exception as exc:  # noqa: BLE001 - adapter records endpoint failures
                last_error = exc
                self.last_attempts.append(
                    {
                        "attempt": attempt + 1,
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    }
                )
                if attempt < 2:
                    time.sleep(2 ** attempt)
        assert last_error is not None
        raise last_error

    def execute(
        self,
        case: BenchmarkCase,
        policy: dict[str, Any],
        model: dict[str, Any],
        condition: str,
        seed: int,
    ) -> ExecutionResult:
        if condition == "metadata_prefilter":
            visible = case.allowed_projection()
        else:
            visible = case.all_fields

        payload = build_chat_payload(
            task=case.user_request,
            visible_data=visible,
            condition=condition,
            policy=policy,
            model=model,
            seed=seed,
        )
        try:
            tick = time.perf_counter()
            data = self._call(payload)
            adapter_latency_ms = round((time.perf_counter() - tick) * 1000, 3)
            text = data["choices"][0]["message"]["content"]
            try:
                parsed = json.loads(text)
                if not isinstance(parsed, dict):
                    parsed = {"unparsed": text}
            except (TypeError, json.JSONDecodeError):
                parsed = {"unparsed": text}
            output_events = validate_structured_output(parsed)
            schema_ok = output_events[0]["status"] == "pass"
            pre_guard_text = text
            if condition == "output_guard_only":
                text, redactions = _guard_output(text, case, policy)
                output_events.append(
                    {
                        "type": "explicit_disclosure_guard",
                        "status": "redacted" if redactions else "pass",
                        "redactions": redactions,
                    }
                )
            usage = data.get("usage", {})
            return ExecutionResult(
                status="ok" if schema_ok else "error",
                raw_response=text,
                parsed_output=parsed,
                accessed_fields=sorted(visible.keys()),
                denied_fields=(
                    sorted(case.forbidden_fields) if condition == "metadata_prefilter" else []
                ),
                output_validation_events=output_events,
                evidence={
                    "condition": condition,
                    "visible_fields": sorted(visible.keys()),
                    "model_request": payload,
                    "model_response": data,
                    "pre_guard_raw_response": pre_guard_text if condition == "output_guard_only" else None,
                },
                token_usage=usage,
                estimated_cost=_usage_cost(usage, model),
                model_version=str(data.get("model", model["name"])),
                adapter_latency_ms=adapter_latency_ms,
                attempts=getattr(self, "last_attempts", []),
                error=None if schema_ok else "model output failed the required structured schema",
            )
        except Exception as exc:  # noqa: BLE001 - adapter boundary returns error evidence
            return ExecutionResult(
                status="error",
                error=str(exc),
                attempts=getattr(self, "last_attempts", []),
            )
