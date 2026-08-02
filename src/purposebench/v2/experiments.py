"""Protocol-v2-local experiment condition semantics and data preparation."""

from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ExperimentCondition(StrEnum):
    FULL_DATA_NO_POLICY = "full_data_no_policy"
    PROMPT_ONLY_RESTRICTION = "prompt_only_restriction"
    OUTPUT_ONLY_GUARD = "output_only_guard"
    ORDINARY_METADATA_PREFILTER = "ordinary_metadata_prefilter"
    COMPEX_GOVERNED_LOCAL = "compex_governed_local"
    COMPEX_GOVERNED_LOCAL_OUTPUT_CONTROLS = (
        "compex_governed_local_output_controls"
    )
    COMPEX_GOVERNED_LOCAL_DP_TRAINING = "compex_governed_local_dp_training"
    COMPEX_GOVERNED_REMOTE = "compex_governed_remote"


class ConditionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    condition: ExperimentCondition
    data_visibility: str
    prompt_restriction: str
    release_enforcement: str
    workload_type: str
    execution_backend: str
    remote_processing: bool
    pseudonymization_required: bool
    approval_binding: bool
    artifact_integrity: bool
    model_integrity: bool
    capability_controls: bool
    privacy_budget: bool
    lineage: bool
    tamper_verifiable_evidence: bool


_UNCONTROLLED = {
    "approval_binding": False,
    "artifact_integrity": False,
    "model_integrity": False,
    "capability_controls": False,
    "privacy_budget": False,
    "lineage": False,
    "tamper_verifiable_evidence": False,
}

_GOVERNED = {
    "approval_binding": True,
    "artifact_integrity": True,
    "model_integrity": True,
    "capability_controls": True,
    "privacy_budget": False,
    "lineage": True,
    "tamper_verifiable_evidence": True,
}


CONDITION_PLANS: dict[ExperimentCondition, ConditionPlan] = {
    ExperimentCondition.FULL_DATA_NO_POLICY: ConditionPlan(
        condition=ExperimentCondition.FULL_DATA_NO_POLICY,
        data_visibility="FULL_RECORD",
        prompt_restriction="NONE",
        release_enforcement="NONE",
        workload_type="INFERENCE",
        execution_backend="DIRECT_LOCAL_MODEL",
        remote_processing=False,
        pseudonymization_required=False,
        **_UNCONTROLLED,
    ),
    ExperimentCondition.PROMPT_ONLY_RESTRICTION: ConditionPlan(
        condition=ExperimentCondition.PROMPT_ONLY_RESTRICTION,
        data_visibility="FULL_RECORD",
        prompt_restriction="PURPOSE_TEXT_ONLY",
        release_enforcement="SCHEMA_ONLY",
        workload_type="INFERENCE",
        execution_backend="DIRECT_LOCAL_MODEL",
        remote_processing=False,
        pseudonymization_required=False,
        **_UNCONTROLLED,
    ),
    ExperimentCondition.OUTPUT_ONLY_GUARD: ConditionPlan(
        condition=ExperimentCondition.OUTPUT_ONLY_GUARD,
        data_visibility="FULL_RECORD",
        prompt_restriction="NONE",
        release_enforcement="POST_HOC_DISCLOSURE_GUARD",
        workload_type="INFERENCE",
        execution_backend="DIRECT_LOCAL_MODEL",
        remote_processing=False,
        pseudonymization_required=False,
        **_UNCONTROLLED,
    ),
    ExperimentCondition.ORDINARY_METADATA_PREFILTER: ConditionPlan(
        condition=ExperimentCondition.ORDINARY_METADATA_PREFILTER,
        data_visibility="APPROVED_PROJECTION",
        prompt_restriction="NONE",
        release_enforcement="SCHEMA_ONLY",
        workload_type="INFERENCE",
        execution_backend="DIRECT_LOCAL_MODEL",
        remote_processing=False,
        pseudonymization_required=False,
        **_UNCONTROLLED,
    ),
    ExperimentCondition.COMPEX_GOVERNED_LOCAL: ConditionPlan(
        condition=ExperimentCondition.COMPEX_GOVERNED_LOCAL,
        data_visibility="APPROVED_PROJECTION",
        prompt_restriction="IMMUTABLE_PURPOSE_CONTRACT",
        release_enforcement="SCHEMA_ONLY",
        workload_type="INFERENCE",
        execution_backend="LOCAL_HARDENED_DOCKER",
        remote_processing=False,
        pseudonymization_required=False,
        **_GOVERNED,
    ),
    ExperimentCondition.COMPEX_GOVERNED_LOCAL_OUTPUT_CONTROLS: ConditionPlan(
        condition=ExperimentCondition.COMPEX_GOVERNED_LOCAL_OUTPUT_CONTROLS,
        data_visibility="APPROVED_PROJECTION",
        prompt_restriction="IMMUTABLE_PURPOSE_CONTRACT",
        release_enforcement="NATIVE_COMPEX_VALIDATORS",
        workload_type="INFERENCE",
        execution_backend="LOCAL_HARDENED_DOCKER",
        remote_processing=False,
        pseudonymization_required=False,
        **_GOVERNED,
    ),
    ExperimentCondition.COMPEX_GOVERNED_LOCAL_DP_TRAINING: ConditionPlan(
        condition=ExperimentCondition.COMPEX_GOVERNED_LOCAL_DP_TRAINING,
        data_visibility="APPROVED_PROJECTION",
        prompt_restriction="IMMUTABLE_PURPOSE_CONTRACT",
        release_enforcement="NATIVE_COMPEX_VALIDATORS",
        workload_type="TRAIN",
        execution_backend="LOCAL_HARDENED_DOCKER",
        remote_processing=False,
        pseudonymization_required=False,
        **{**_GOVERNED, "privacy_budget": True},
    ),
    ExperimentCondition.COMPEX_GOVERNED_REMOTE: ConditionPlan(
        condition=ExperimentCondition.COMPEX_GOVERNED_REMOTE,
        data_visibility="APPROVED_PROJECTION",
        prompt_restriction="IMMUTABLE_PURPOSE_CONTRACT",
        release_enforcement="NATIVE_COMPEX_VALIDATORS",
        workload_type="INFERENCE",
        execution_backend="REMOTE_COMMERCIAL_MODEL",
        remote_processing=True,
        pseudonymization_required=True,
        **_GOVERNED,
    ),
}


class PreparedConditionInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    condition: ExperimentCondition
    fields: dict[str, Any]
    transmitted_fields: tuple[str, ...]
    denied_fields: tuple[str, ...]
    pseudonymized_fields: tuple[str, ...]
    processing_classification: str


_DIRECT_IDENTIFIER = re.compile(
    r"(^|_)(case|customer|complaint|record|account|application|loan|person)_?id$|^lei$",
    re.IGNORECASE,
)


def _validated_projection(
    all_fields: Mapping[str, Any],
    allowed_fields: Sequence[str],
    denied_fields: Sequence[str],
) -> dict[str, Any]:
    allowed = tuple(allowed_fields)
    denied = tuple(denied_fields)
    if not allowed or len(set(allowed)) != len(allowed):
        raise ValueError("allowed fields must be nonempty and unique")
    if len(set(denied)) != len(denied):
        raise ValueError("denied fields must be unique")
    overlap = sorted(set(allowed) & set(denied))
    if overlap:
        raise ValueError(f"fields cannot be both allowed and denied: {overlap}")
    unknown = sorted((set(allowed) | set(denied)) - set(all_fields))
    if unknown:
        raise ValueError(f"condition references unknown fields: {unknown}")
    return {field: all_fields[field] for field in allowed}


def _pseudonymize(value: Any, salt: bytes) -> str:
    return "pseudo_" + hmac.new(
        salt,
        str(value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:24]


def prepare_condition_input(
    *,
    condition: ExperimentCondition,
    all_fields: Mapping[str, Any],
    allowed_fields: Sequence[str],
    denied_fields: Sequence[str],
    pseudonymization_salt: bytes | None = None,
) -> PreparedConditionInput:
    """Apply the declared input semantics without weakening any baseline."""

    plan = CONDITION_PLANS[condition]
    projection = _validated_projection(all_fields, allowed_fields, denied_fields)
    if plan.data_visibility == "FULL_RECORD":
        visible = dict(all_fields)
        effective_denied: tuple[str, ...] = ()
    else:
        visible = projection
        effective_denied = tuple(sorted(denied_fields))

    pseudonymized: list[str] = []
    if plan.pseudonymization_required:
        if pseudonymization_salt is None or len(pseudonymization_salt) < 16:
            raise ValueError("remote processing requires a 16-byte pseudonymization salt")
        for field in sorted(visible):
            if _DIRECT_IDENTIFIER.search(field) and visible[field] is not None:
                visible[field] = _pseudonymize(visible[field], pseudonymization_salt)
                pseudonymized.append(field)

    return PreparedConditionInput(
        condition=condition,
        fields=visible,
        transmitted_fields=tuple(sorted(visible)),
        denied_fields=effective_denied,
        pseudonymized_fields=tuple(pseudonymized),
        processing_classification=(
            "REMOTE_PROVIDER_PROCESSING"
            if plan.remote_processing
            else "LOCAL_MODEL_PROCESSING"
        ),
    )


def validate_condition_matrix() -> None:
    expected = set(ExperimentCondition)
    if set(CONDITION_PLANS) != expected or len(CONDITION_PLANS) != 8:
        raise RuntimeError("protocol-v2-local condition matrix is incomplete")
    ordinary = CONDITION_PLANS[ExperimentCondition.ORDINARY_METADATA_PREFILTER]
    governed = CONDITION_PLANS[ExperimentCondition.COMPEX_GOVERNED_LOCAL]
    if ordinary.data_visibility != governed.data_visibility:
        raise RuntimeError("ordinary metadata filtering is not a fair projection baseline")
    if any(
        getattr(ordinary, field)
        for field in (
            "approval_binding",
            "artifact_integrity",
            "model_integrity",
            "capability_controls",
            "lineage",
            "tamper_verifiable_evidence",
        )
    ):
        raise RuntimeError("ordinary filtering was incorrectly given Compex controls")


validate_condition_matrix()
