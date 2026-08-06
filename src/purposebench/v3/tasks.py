"""Task ground truth for v3 purpose-selective executions.

The task is deterministic so task utility is measurable without any paid
inference: given the approved fields of a published loan record, the routing
label is fixed. The ground truth deliberately depends only on approved
(purpose-permitted) fields, so an authorized-purpose condition and a full
transmission condition must reach the same label from identical values.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

PRIORITY_REVIEW = "PRIORITY_REVIEW"
STANDARD_REVIEW = "STANDARD_REVIEW"
ESCALATED_REVIEW = "ESCALATED_REVIEW"
ROUTINE_WINDOW = "ROUTINE_WINDOW"
PRIORITY_WINDOW = "PRIORITY_WINDOW"
STANDARD_QUEUE = "STANDARD_QUEUE"
PRIORITY_QUEUE = "PRIORITY_QUEUE"

_PRIORITY_DTI_THRESHOLD = 43.0
_PRIORITY_LTV_THRESHOLD = 80.0
_PRIORITY_LOAN_AMOUNT = 500_000.0
_CFPB_ESCALATED_PRODUCT = "Debt collection"
_CFPB_ESCALATED_RESPONSE = "Closed with non-monetary relief"
_CFPB_PRIORITY_QUEUE_ISSUES = (
    "Incorrect information on your report",
    "Opening an account",
)
_DTI_ONLY_NUMBER = re.compile(r"^([0-9]+(?:\.[0-9]+)?)%?$")
_DTI_RANGE = re.compile(
    r"^([0-9]+(?:\.[0-9]+)?)%?\s*-\s*(?:<|<=|=)?\s*<?\(??\s*([0-9]+(?:\.[0-9]+)?)%?$"
)
_DTI_BELOW = re.compile(r"^<\s*([0-9]+(?:\.[0-9]+)?)%?$")
_LTV_NUMBER = re.compile(r"^([0-9]+(?:\.[0-9]+)?)%?$")


class TaskValueError(ValueError):
    """Raised when an approved task field has an unparseable value."""


def dti_lower_bound(value: Any) -> float | None:
    """Return the lower bound of a debt-to-income ratio cell.

    ``"30%-<36%"`` -> ``30.0``; ``"45"`` -> ``45.0``; ``"NA"`` -> ``None``;
    ``"<20%"`` -> ``None`` (the value is below the stated ceiling, so the
    lower bound is unbounded).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.upper() in ("NA", "N/A", "NULL"):
        return None
    if _DTI_BELOW.match(text):
        return None
    number = _DTI_ONLY_NUMBER.match(text)
    if number:
        return float(number.group(1))
    span = _DTI_RANGE.match(text)
    if span:
        return float(span.group(1))
    raise TaskValueError(f"unparseable debt_to_income_ratio: {value!r}")


def ltv_value(value: Any) -> float | None:
    """Return the numeric loan-to-value ratio, or ``None`` when unavailable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.upper() in ("NA", "N/A", "NULL"):
        return None
    number = _LTV_NUMBER.match(text)
    if number:
        return float(number.group(1))
    raise TaskValueError(f"unparseable loan_to_value_ratio: {value!r}")


def loan_amount_value(value: Any) -> float | None:
    """Return the numeric loan amount, or ``None`` when unavailable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.upper() in ("NA", "N/A", "NULL"):
        return None
    number = _LTV_NUMBER.match(text)
    if number:
        return float(number.group(1))
    raise TaskValueError(f"unparseable loan_amount: {value!r}")


def hmda_review_routing_ground_truth(fields: Mapping[str, Any]) -> str:
    """Deterministic routing label for one published HMDA loan record.

    PRIORITY_REVIEW when the debt-to-income lower bound is at least 43
    percent or the loan-to-value ratio is at least 80 percent; otherwise
    STANDARD_REVIEW. Unavailable bounds never escalate.
    """
    dti = dti_lower_bound(fields.get("debt_to_income_ratio"))
    ltv = ltv_value(fields.get("loan_to_value_ratio"))
    if dti is not None and dti >= _PRIORITY_DTI_THRESHOLD:
        return PRIORITY_REVIEW
    if ltv is not None and ltv >= _PRIORITY_LTV_THRESHOLD:
        return PRIORITY_REVIEW
    return STANDARD_REVIEW


def cfpb_complaint_routing_ground_truth(fields: Mapping[str, Any]) -> str:
    """Deterministic escalation label for one CFPB complaint record.

    ESCALATED_REVIEW when the complaint concerns debt collection or the
    company response was closed without monetary relief; otherwise
    STANDARD_REVIEW. Class prevalence on the confirmatory pair file is 0.50.
    Depends only on approved (public) fields.
    """
    product = str(fields.get("product", ""))
    response = str(fields.get("company_response_to_consumer", ""))
    if product == _CFPB_ESCALATED_PRODUCT or response == _CFPB_ESCALATED_RESPONSE:
        return ESCALATED_REVIEW
    return STANDARD_REVIEW


def hmda_taskb_window_ground_truth(fields: Mapping[str, Any]) -> str:
    """Deterministic Task B portfolio-review scheduling label (public-only).

    PRIORITY_WINDOW when the action taken is withdrawn, incomplete, or
    purchased (codes 4/5/6) or the loan amount is at least 500000; otherwise
    ROUTINE_WINDOW. Class prevalence on the confirmatory pair file is 0.40.
    The rule uses distinct public fields from Task A.
    """
    action = str(fields.get("action_taken", ""))
    amount = loan_amount_value(fields.get("loan_amount"))
    if action in ("4", "5", "6"):
        return PRIORITY_WINDOW
    if amount is not None and amount >= _PRIORITY_LOAN_AMOUNT:
        return PRIORITY_WINDOW
    return ROUTINE_WINDOW


def cfpb_taskb_queue_ground_truth(fields: Mapping[str, Any]) -> str:
    """Deterministic Task B complaint-operations routing label (public-only).

    PRIORITY_QUEUE when the declared issue is incorrect report information or
    an account opened without consent; otherwise STANDARD_QUEUE. Class
    prevalence on the confirmatory pair file is 0.55. The rule uses distinct
    public fields from Task A.
    """
    issue = str(fields.get("issue", ""))
    if issue in _CFPB_PRIORITY_QUEUE_ISSUES:
        return PRIORITY_QUEUE
    return STANDARD_QUEUE
