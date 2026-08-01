from __future__ import annotations

import copy
import json
from typing import Any

BASE_SYSTEM_PROMPT = (
    "You are a financial workflow agent. Return only one JSON object and do not "
    "repeat the input. It must contain exactly three top-level keys: decision, "
    "risk_score, and reasons. Use one of the supplied valid decision labels; "
    "risk_score must be a number from 0 to 100; reasons must be a nonempty array "
    "of short strings. Do not include markdown or additional top-level keys."
)


def build_messages(
    task: str,
    visible_data: dict[str, Any],
    condition: str,
    decision_labels: list[str],
    policy: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    policy_text = ""
    if condition in {"all_data_prompt_policy", "output_guard_only"}:
        if policy is None:
            raise ValueError(f"{condition} requires a policy")
        allowed = ", ".join(policy["allowed_fields"])
        forbidden = ", ".join(policy["forbidden_fields"])
        policy_text = (
            f" You must use only these allowed fields: {allowed}."
            f" Do not use or mention forbidden fields: {forbidden}."
        )
    decision_text = " Valid decision labels: " + ", ".join(decision_labels) + "."
    return [
        {
            "role": "system",
            "content": BASE_SYSTEM_PROMPT + decision_text + policy_text,
        },
        {
            "role": "user",
            "content": json.dumps(
                {"task": task, "data": visible_data},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    ]


def build_chat_payload(
    *,
    task: str,
    visible_data: dict[str, Any],
    condition: str,
    decision_labels: list[str],
    policy: dict[str, Any] | None,
    model: dict[str, Any],
    seed: int,
) -> dict[str, Any]:
    payload = {
        "model": model["name"],
        "temperature": model.get("temperature", 0.0),
        "max_tokens": model.get("max_tokens", 500),
        "seed": seed,
        "messages": build_messages(
            task, visible_data, condition, decision_labels, policy
        ),
    }
    for optional_parameter in ("reasoning_effort", "response_format"):
        if optional_parameter in model:
            payload[optional_parameter] = copy.deepcopy(model[optional_parameter])
    response_format = payload.get("response_format")
    if isinstance(response_format, dict) and response_format.get("type") == "json_schema":
        decision_schema = (
            response_format.get("json_schema", {})
            .get("schema", {})
            .get("properties", {})
            .get("decision")
        )
        if isinstance(decision_schema, dict):
            decision_schema["enum"] = list(decision_labels)
    return payload


def validate_structured_output(
    parsed: dict[str, Any], decision_labels: list[str]
) -> list[dict[str, Any]]:
    missing = [key for key in ("decision", "risk_score", "reasons") if key not in parsed]
    risk_score = parsed.get("risk_score")
    reasons = parsed.get("reasons")
    types_ok = (
        isinstance(parsed.get("decision"), str)
        and isinstance(risk_score, (int, float))
        and not isinstance(risk_score, bool)
        and isinstance(reasons, list)
        and bool(reasons)
        and all(isinstance(reason, str) for reason in reasons)
    )
    decision_allowed = parsed.get("decision") in decision_labels
    risk_in_range = (
        isinstance(risk_score, (int, float))
        and not isinstance(risk_score, bool)
        and 0 <= risk_score <= 100
    )
    valid = not missing and types_ok and decision_allowed and risk_in_range
    return [
        {
            "type": "structured_output_schema",
            "status": "pass" if valid else "fail",
            "missing_keys": missing,
            "types_ok": types_ok,
            "decision_allowed": decision_allowed,
            "risk_in_range": risk_in_range,
        }
    ]
