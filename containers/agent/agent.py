#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from prompts import build_chat_payload, validate_structured_output

INPUT_PATH = Path("/input/projected.json")
OUTPUT_PATH = Path("/output/result.json")
RESULT_PREFIX = "PURPOSEBENCH_RESULT_JSON="


def _json_env(name: str) -> Any:
    try:
        return json.loads(os.environ[name])
    except KeyError as exc:
        raise RuntimeError(f"missing required environment variable {name}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON in {name}: {exc}") from exc


def _hash_json(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _model_call(url: str, api_key: str, payload: dict[str, Any], timeout: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    last_error: Exception | None = None
    request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(1, 4):
        tick = time.perf_counter()
        headers = {"content-type": "application/json"}
        if api_key:
            headers["authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            f"{url.rstrip('/')}/chat/completions",
            data=request_body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_body = response.read()
                attempts.append(
                    {
                        "attempt": attempt,
                        "status": "ok",
                        "http_status": response.status,
                        "latency_ms": round((time.perf_counter() - tick) * 1000, 3),
                    }
                )
                return json.loads(response_body), attempts
        except Exception as exc:  # noqa: BLE001 - process boundary records every failure
            last_error = exc
            http_status = exc.code if isinstance(exc, urllib.error.HTTPError) else None
            attempts.append(
                {
                    "attempt": attempt,
                    "status": "error",
                    "http_status": http_status,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "latency_ms": round((time.perf_counter() - tick) * 1000, 3),
                }
            )
            if attempt < 3:
                time.sleep(2 ** (attempt - 1))
    assert last_error is not None
    raise RuntimeError(f"model call failed after 3 attempts: {last_error}")


def main() -> int:
    started = time.perf_counter()
    try:
        projection = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
        allowed_fields = [str(value) for value in _json_env("PURPOSEBENCH_ALLOWED_FIELDS")]
        forbidden_fields = [str(value) for value in _json_env("PURPOSEBENCH_FORBIDDEN_FIELDS")]
        sentinels = [str(value) for value in _json_env("PURPOSEBENCH_SENTINELS")]
        decision_labels = [
            str(value) for value in _json_env("PURPOSEBENCH_DECISION_LABELS")
        ]
        columns = [str(value) for value in projection.get("columns", [])]
        rows = projection.get("rows", [])
        if projection.get("rowCount") != 1 or len(rows) != 1:
            raise RuntimeError("projection must contain exactly one row")
        if set(columns) != set(allowed_fields) or len(columns) != len(allowed_fields):
            raise RuntimeError(
                f"projected columns mismatch: expected={sorted(allowed_fields)} actual={sorted(columns)}"
            )
        visible = {
            key: _restore_json_value(value)
            for key, value in rows[0].items()
        }
        if set(visible) != set(allowed_fields):
            raise RuntimeError("projected row keys differ from the policy-allowed fields")
        leaked = sorted(set(visible) & set(forbidden_fields))
        if leaked:
            raise RuntimeError(f"forbidden fields present in projection: {leaked}")

        requested_model = os.environ["PURPOSEBENCH_MODEL"]
        seed = int(os.environ["PURPOSEBENCH_SEED"])
        model = {
            "name": requested_model,
            "temperature": float(os.environ.get("PURPOSEBENCH_TEMPERATURE", "0")),
            "max_tokens": int(os.environ.get("PURPOSEBENCH_MAX_TOKENS", "500")),
        }
        reasoning_effort = os.environ.get("PURPOSEBENCH_REASONING_EFFORT")
        if reasoning_effort:
            model["reasoning_effort"] = reasoning_effort
        response_format = os.environ.get("PURPOSEBENCH_RESPONSE_FORMAT")
        if response_format:
            model["response_format"] = json.loads(response_format)
        model_request = build_chat_payload(
            task=os.environ["PURPOSEBENCH_TASK"],
            visible_data=visible,
            condition="compex_purpose_bound",
            decision_labels=decision_labels,
            policy=None,
            model=model,
            seed=seed,
        )
        model_response, attempts = _model_call(
            os.environ["MODEL_BASE_URL"],
            os.environ.get("MODEL_API_KEY", ""),
            model_request,
            float(os.environ.get("MODEL_TIMEOUT_SECONDS", "180")),
        )
        message = model_response["choices"][0]["message"]
        raw_output = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []
        try:
            parsed_output = json.loads(raw_output)
            if not isinstance(parsed_output, dict):
                parsed_output = {"unparsed": raw_output}
        except (TypeError, json.JSONDecodeError):
            parsed_output = {"unparsed": raw_output}

        validation_events = validate_structured_output(parsed_output, decision_labels)
        disclosed = [value for value in sentinels if value and value in raw_output]
        validation_events.append(
            {
                "type": "forbidden_sentinel_scan",
                "status": "fail" if disclosed else "pass",
                "matched_sentinel_hashes": [hashlib.sha256(v.encode()).hexdigest() for v in disclosed],
            }
        )
        schema_ok = validation_events[0]["status"] == "pass"
        result = {
            "schema_version": "1.0",
            "status": "ok" if schema_ok else "error",
            "error": None if schema_ok else "model output failed the required structured schema",
            "requested_model": requested_model,
            "model_identifier": str(model_response.get("model", requested_model)),
            "seed": seed,
            "model_request": model_request,
            "model_request_hash": _hash_json(model_request),
            "model_response": model_response,
            "raw_output": raw_output,
            "parsed_output": parsed_output,
            "tool_calls": tool_calls,
            "accessed_fields": sorted(visible),
            "denied_fields": sorted(forbidden_fields),
            "policy_events": [
                {
                    "type": "purpose_projection_consumed",
                    "status": "allow",
                    "allowed_fields": sorted(visible),
                    "denied_fields": sorted(forbidden_fields),
                    "projection_hash": _hash_json(visible),
                }
            ],
            "output_validation_events": validation_events,
            "token_usage": model_response.get("usage", {}),
            "attempts": attempts,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    except Exception as exc:  # noqa: BLE001 - entrypoint must emit a structured error
        result = {
            "schema_version": "1.0",
            "status": "error",
            "error": str(exc),
            "raw_output": "",
            "parsed_output": {},
            "tool_calls": [],
            "accessed_fields": [],
            "denied_fields": [],
            "policy_events": [],
            "output_validation_events": [],
            "token_usage": {},
            "attempts": [],
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(RESULT_PREFIX + output, flush=True)
    return 0


def _restore_json_value(value: Any) -> Any:
    if not isinstance(value, str) or not value.startswith(("[", "{")):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


if __name__ == "__main__":
    sys.exit(main())
