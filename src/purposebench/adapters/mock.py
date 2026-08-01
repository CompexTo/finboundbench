from __future__ import annotations

from typing import Any

from purposebench.adapters.base import Adapter
from purposebench.models import BenchmarkCase, ExecutionResult


class MockAdapter(Adapter):
    """Deterministic harness test. Not valid as a research result."""

    def execute(
        self,
        case: BenchmarkCase,
        policy: dict[str, Any],
        model: dict[str, Any],
        condition: str,
        seed: int,
    ) -> ExecutionResult:
        visible = case.allowed_projection() if condition in {"metadata_prefilter", "compex_purpose_bound"} else case.all_fields
        decision = case.ground_truth["decision"]
        if condition in {"all_data_no_policy", "all_data_prompt_policy", "output_guard_only"} and case.variant == "B":
            # Intentional vulnerability used only to test metric sensitivity.
            decision = "manual_review" if case.workflow == "credit_underwriting" else decision
        return ExecutionResult(
            status="ok",
            raw_response=str({"decision": decision, "risk_score": 50, "reasons": []}),
            parsed_output={"decision": decision, "risk_score": 50, "reasons": []},
            accessed_fields=sorted(visible),
            denied_fields=(
                sorted(case.forbidden_fields)
                if condition in {"metadata_prefilter", "compex_purpose_bound"}
                else []
            ),
            policy_events=[{"action": "project", "allowed": sorted(visible)}],
            output_validation_events=[{"type": "mock_schema", "status": "pass"}],
            evidence={"mock": True, "visible_fields": sorted(visible)},
            model_version=str(model.get("name", "mock")),
            attempts=[{"attempt": 1, "status": "ok"}],
        )
