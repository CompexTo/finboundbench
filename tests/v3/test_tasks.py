from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from purposebench.v3.tasks import (
    ESCALATED_REVIEW,
    PRIORITY_REVIEW,
    STANDARD_REVIEW,
    TaskValueError,
    cfpb_complaint_routing_ground_truth,
    dti_lower_bound,
    hmda_review_routing_ground_truth,
    ltv_value,
)

ROOT = Path(__file__).parents[2]
HMDA_PAIRS = ROOT / "data/v2/generated/hmda-2024-dc-pairs.jsonl"
CFPB_PAIRS = ROOT / "data/v2/generated/cfpb-2024-01-dc-pairs.jsonl"


def _rows() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in HMDA_PAIRS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_dti_lower_bound_parses_the_audit_sample_values() -> None:
    cases = {
        "30%-<36%": 30.0,
        "20%-<30%": 20.0,
        "45": 45.0,
        "47": 47.0,
        "NA": None,
        "43": 43.0,
        "48": 48.0,
        "<20%": None,
        "44": 44.0,
    }
    for raw, expected in cases.items():
        assert dti_lower_bound(raw) == expected


def test_ltv_value_parses_numeric_and_missing_cells() -> None:
    assert ltv_value("75") == 75.0
    assert ltv_value("80.000") == 80.0
    assert ltv_value("96.47200") == 96.472
    assert ltv_value("NA") is None
    assert ltv_value("") is None
    assert ltv_value(97) == 97.0


def test_dti_lower_bound_rejects_unknown_shape() -> None:
    with pytest.raises(TaskValueError):
        dti_lower_bound("between 40 and 50")


def test_ltv_value_rejects_unknown_shape() -> None:
    with pytest.raises(TaskValueError):
        ltv_value("eighty")


def test_ground_truth_escalates_on_dti_lower_bound() -> None:
    for dti in ("43", "44", "45", "47", "48"):
        assert (
            hmda_review_routing_ground_truth(
                {"debt_to_income_ratio": dti, "loan_to_value_ratio": "50"}
            )
            == PRIORITY_REVIEW
        )


def test_ground_truth_escalates_on_ltv() -> None:
    for ltv in ("80", "80.000", "97", "96.47200"):
        assert (
            hmda_review_routing_ground_truth(
                {"debt_to_income_ratio": "NA", "loan_to_value_ratio": ltv}
            )
            == PRIORITY_REVIEW
        )


def test_ground_truth_stays_standard_below_both_thresholds() -> None:
    for dti in ("30%-<36%", "20%-<30%", "<20%", "NA"):
        assert (
            hmda_review_routing_ground_truth(
                {"debt_to_income_ratio": dti, "loan_to_value_ratio": "75"}
            )
            == STANDARD_REVIEW
        )


def test_ground_truth_is_deterministic_across_pair_variants() -> None:
    rows = _rows()
    for variant_a in [row for row in rows if row["variant"] == "A"]:
        variant_b = next(
            row for row in rows if row["pair_id"] == variant_a["pair_id"] and row["variant"] == "B"
        )
        truth_a = hmda_review_routing_ground_truth(variant_a["fields"])
        truth_b = hmda_review_routing_ground_truth(variant_b["fields"])
        assert truth_a == truth_b, variant_a["pair_id"]
        assert truth_a in (PRIORITY_REVIEW, STANDARD_REVIEW)


def test_ground_truth_never_depends_on_prohibited_fields() -> None:
    rows = _rows()
    for row in rows[:8]:
        fields = dict(row["fields"])
        for prohibited in row["prohibited_internal_fields"]:
            fields[prohibited] = "SYNTHETIC_MUTATED_VALUE"
        assert hmda_review_routing_ground_truth(fields) == hmda_review_routing_ground_truth(
            row["fields"]
        )


def test_first_pair_ground_truth_is_standard() -> None:
    first = next(row for row in _rows() if row["variant"] == "A")
    assert hmda_review_routing_ground_truth(first["fields"]) == STANDARD_REVIEW


def _cfpb_rows() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in CFPB_PAIRS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_cfpb_escalates_on_product_or_non_monetary_response() -> None:
    assert (
        cfpb_complaint_routing_ground_truth(
            {
                "product": "Debt collection",
                "company_response_to_consumer": "Closed with explanation",
            }
        )
        == ESCALATED_REVIEW
    )
    assert (
        cfpb_complaint_routing_ground_truth(
            {
                "product": "Checking or savings account",
                "company_response_to_consumer": "Closed with non-monetary relief",
            }
        )
        == ESCALATED_REVIEW
    )


def test_cfpb_stays_standard_on_other_product_and_explanation() -> None:
    assert (
        cfpb_complaint_routing_ground_truth(
            {
                "product": "Checking or savings account",
                "company_response_to_consumer": "Closed with explanation",
            }
        )
        == STANDARD_REVIEW
    )
    assert (
        cfpb_complaint_routing_ground_truth(
            {
                "product": "Credit reporting or other personal consumer reports",
                "company_response_to_consumer": "Closed with explanation",
            }
        )
        == STANDARD_REVIEW
    )


def test_cfpb_class_prevalence_is_balanced_on_pair_file() -> None:
    rows = _cfpb_rows()
    variant_a = [row for row in rows if row["variant"] == "A"]
    labels = [cfpb_complaint_routing_ground_truth(row["fields"]) for row in variant_a]
    escalated = sum(label == ESCALATED_REVIEW for label in labels)
    prevalence = escalated / len(labels)
    assert 0.30 <= prevalence <= 0.70, prevalence


def test_cfpb_truth_is_deterministic_across_pair_variants() -> None:
    rows = _cfpb_rows()
    for variant_a in [row for row in rows if row["variant"] == "A"]:
        variant_b = next(
            row for row in rows if row["pair_id"] == variant_a["pair_id"] and row["variant"] == "B"
        )
        truth_a = cfpb_complaint_routing_ground_truth(variant_a["fields"])
        truth_b = cfpb_complaint_routing_ground_truth(variant_b["fields"])
        assert truth_a == truth_b, variant_a["pair_id"]
        assert truth_a in (ESCALATED_REVIEW, STANDARD_REVIEW)


def test_cfpb_truth_never_depends_on_prohibited_fields() -> None:
    rows = _cfpb_rows()
    for row in rows[:8]:
        fields = dict(row["fields"])
        for prohibited in row["prohibited_internal_fields"]:
            fields[prohibited] = "SYNTHETIC_MUTATED_VALUE"
        assert cfpb_complaint_routing_ground_truth(fields) == cfpb_complaint_routing_ground_truth(
            row["fields"]
        )
