from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BenchmarkCase(BaseModel):
    case_id: str
    pair_id: str
    workflow: str
    purpose: str
    variant: str
    attack_class: str
    user_request: str
    all_fields: dict[str, Any]
    allowed_fields: list[str]
    forbidden_fields: list[str]
    ground_truth: dict[str, Any]
    sentinel_values: list[str] = Field(default_factory=list)

    def allowed_projection(self) -> dict[str, Any]:
        return {k: self.all_fields[k] for k in self.allowed_fields if k in self.all_fields}


class ExecutionResult(BaseModel):
    status: Literal["ok", "error"]
    raw_response: str = ""
    parsed_output: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    accessed_fields: list[str] = Field(default_factory=list)
    denied_fields: list[str] = Field(default_factory=list)
    policy_events: list[dict[str, Any]] = Field(default_factory=list)
    output_validation_events: list[dict[str, Any]] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    token_usage: dict[str, Any] = Field(default_factory=dict)
    estimated_cost: float | None = None
    model_version: str | None = None
    compex_run_id: str | None = None
    evidence_id: str | None = None
    adapter_latency_ms: float | None = None
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
