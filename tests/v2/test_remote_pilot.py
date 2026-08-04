from pathlib import Path

from purposebench.utils import sha256_file
from purposebench.v2.experiments import ExperimentCondition
from purposebench.v2.inference_pilot import condition_prompts, load_paired_records
from purposebench.v2.remote_pilot import prepare_remote_batch


def _dataset_path() -> Path:
    return Path("data/v2/generated/hmda-2024-dc-pairs.jsonl")


def test_remote_batch_denies_internal_fields_and_pseudonymizes_identifiers() -> None:
    dataset = _dataset_path()
    rows = load_paired_records(dataset, pair_limit=2)
    first, selected, denied, pseudonymized = prepare_remote_batch(
        rows,
        dataset_sha256=sha256_file(dataset),
    )
    second, _, _, _ = prepare_remote_batch(
        rows,
        dataset_sha256=sha256_file(dataset),
    )
    assert first == second
    assert set(denied).isdisjoint(selected)
    assert set(denied).isdisjoint(first[0])
    assert {"case_id", "lei", "source_record_id"}.issubset(pseudonymized)
    assert first[0]["case_id"].startswith("pseudo_")
    assert first[0]["case_id"] != rows[0]["case_id"]


def test_remote_prompt_uses_the_immutable_purpose_contract() -> None:
    prompt = condition_prompts(
        ExperimentCondition.COMPEX_GOVERNED_REMOTE,
        ("internal_fraud_note",),
    )["system"]
    assert "Immutable purpose contract" in prompt
    assert "No tools or network calls are authorized" in prompt
