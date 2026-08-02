import pytest

from purposebench.v2.experiments import (
    CONDITION_PLANS,
    ExperimentCondition,
    prepare_condition_input,
    validate_condition_matrix,
)

FIELDS = {
    "case_id": "case-001",
    "loan_amount": 125000,
    "debt_to_income_ratio": 0.31,
    "internal_fraud_note": "SYNTHETIC_INTERNAL_SENTINEL",
}
ALLOWED = ("case_id", "loan_amount", "debt_to_income_ratio")
DENIED = ("internal_fraud_note",)


def test_matrix_contains_all_eight_required_conditions() -> None:
    validate_condition_matrix()
    assert len(CONDITION_PLANS) == 8
    assert set(CONDITION_PLANS) == set(ExperimentCondition)


def test_ordinary_prefilter_is_honest_but_has_weaker_evidence() -> None:
    ordinary = prepare_condition_input(
        condition=ExperimentCondition.ORDINARY_METADATA_PREFILTER,
        all_fields=FIELDS,
        allowed_fields=ALLOWED,
        denied_fields=DENIED,
    )
    governed = prepare_condition_input(
        condition=ExperimentCondition.COMPEX_GOVERNED_LOCAL,
        all_fields=FIELDS,
        allowed_fields=ALLOWED,
        denied_fields=DENIED,
    )

    assert ordinary.fields == governed.fields
    assert "internal_fraud_note" not in ordinary.fields
    assert CONDITION_PLANS[ordinary.condition].artifact_integrity is False
    assert CONDITION_PLANS[governed.condition].artifact_integrity is True
    assert CONDITION_PLANS[governed.condition].approval_binding is True


@pytest.mark.parametrize(
    "condition",
    [
        ExperimentCondition.FULL_DATA_NO_POLICY,
        ExperimentCondition.PROMPT_ONLY_RESTRICTION,
        ExperimentCondition.OUTPUT_ONLY_GUARD,
    ],
)
def test_non_projection_baselines_receive_the_full_record(
    condition: ExperimentCondition,
) -> None:
    prepared = prepare_condition_input(
        condition=condition,
        all_fields=FIELDS,
        allowed_fields=ALLOWED,
        denied_fields=DENIED,
    )
    assert prepared.fields == FIELDS
    assert prepared.denied_fields == ()


def test_remote_condition_transmits_only_pseudonymized_projection() -> None:
    prepared = prepare_condition_input(
        condition=ExperimentCondition.COMPEX_GOVERNED_REMOTE,
        all_fields=FIELDS,
        allowed_fields=ALLOWED,
        denied_fields=DENIED,
        pseudonymization_salt=b"research-only-salt",
    )

    assert prepared.processing_classification == "REMOTE_PROVIDER_PROCESSING"
    assert prepared.fields["case_id"].startswith("pseudo_")
    assert prepared.fields["case_id"] != FIELDS["case_id"]
    assert prepared.pseudonymized_fields == ("case_id",)
    assert "internal_fraud_note" not in prepared.fields


def test_remote_condition_fails_without_sufficient_salt() -> None:
    with pytest.raises(ValueError, match="16-byte"):
        prepare_condition_input(
            condition=ExperimentCondition.COMPEX_GOVERNED_REMOTE,
            all_fields=FIELDS,
            allowed_fields=ALLOWED,
            denied_fields=DENIED,
            pseudonymization_salt=b"short",
        )


def test_unknown_or_overlapping_fields_fail_closed() -> None:
    with pytest.raises(ValueError, match="both allowed and denied"):
        prepare_condition_input(
            condition=ExperimentCondition.COMPEX_GOVERNED_LOCAL,
            all_fields=FIELDS,
            allowed_fields=("case_id",),
            denied_fields=("case_id",),
        )
    with pytest.raises(ValueError, match="unknown fields"):
        prepare_condition_input(
            condition=ExperimentCondition.COMPEX_GOVERNED_LOCAL,
            all_fields=FIELDS,
            allowed_fields=("missing",),
            denied_fields=DENIED,
        )
