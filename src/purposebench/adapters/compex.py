from __future__ import annotations

import os
import shlex
import subprocess
from typing import Any

import httpx

from purposebench.adapters.base import Adapter
from purposebench.models import BenchmarkCase, ExecutionResult


class CompexAdapter(Adapter):
    """Generic local Compex adapter.

    Codex must map the request and response fields to the actual local Compex interface.
    The default HTTP shape is intentionally explicit and fails on missing evidence.
    """

    def __init__(self) -> None:
        self.mode = os.getenv("COMPEX_MODE", "http")
        self.base_url = os.getenv("COMPEX_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
        self.execute_path = os.getenv("COMPEX_EXECUTE_PATH", "/api/v1/research/execute")
        self.api_key = os.getenv("COMPEX_API_KEY", "")
        self.cli_command = os.getenv("COMPEX_CLI_COMMAND", "")

    def execute(
        self,
        case: BenchmarkCase,
        policy: dict[str, Any],
        model: dict[str, Any],
        condition: str,
        seed: int,
    ) -> ExecutionResult:
        payload = {
            "purpose": case.purpose,
            "task": case.user_request,
            "objects": case.all_fields,
            "policy": policy,
            "model": model,
            "seed": seed,
            "metadata": {
                "case_id": case.case_id,
                "pair_id": case.pair_id,
                "synthetic": True,
            },
        }
        try:
            if self.mode == "cli":
                if not self.cli_command:
                    raise RuntimeError("COMPEX_CLI_COMMAND is empty")
                proc = subprocess.run(
                    shlex.split(self.cli_command),
                    input=__import__("json").dumps(payload),
                    text=True,
                    capture_output=True,
                    check=True,
                )
                data = __import__("json").loads(proc.stdout)
            else:
                headers = {"Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                with httpx.Client(timeout=300) as client:
                    response = client.post(
                        f"{self.base_url}{self.execute_path}", headers=headers, json=payload
                    )
                    response.raise_for_status()
                    data = response.json()

            evidence = data.get("evidence") or data.get("audit")
            if not evidence:
                raise RuntimeError("Compex response did not include evidence/audit data")
            return ExecutionResult(
                status="ok",
                raw_response=data.get("output", data.get("raw_response", "")),
                parsed_output=data.get("parsed_output", data.get("result", {})),
                tool_calls=data.get("tool_calls", []),
                accessed_fields=data.get("accessed_fields", data.get("exposed_fields", [])),
                policy_events=data.get("policy_events", []),
                evidence=evidence,
                token_usage=data.get("token_usage", {}),
                estimated_cost=data.get("estimated_cost"),
            )
        except Exception as exc:
            return ExecutionResult(status="error", error=str(exc))
