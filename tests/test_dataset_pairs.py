from pathlib import Path

from purposebench.dataset.generate import generate_dataset
from purposebench.dataset.select import select_stratified_cases
from purposebench.models import BenchmarkCase
from purposebench.utils import canonical_json, read_jsonl


def test_pairs_share_allowed_projection(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    generate_dataset(path, cases_per_workflow=2, seed=123)
    cases = [BenchmarkCase.model_validate(row) for row in read_jsonl(path)]
    pairs: dict[str, list[BenchmarkCase]] = {}
    for case in cases:
        pairs.setdefault(case.pair_id, []).append(case)
    for pair in pairs.values():
        assert len(pair) == 2
        assert canonical_json(pair[0].allowed_projection()) == canonical_json(
            pair[1].allowed_projection()
        )
        assert pair[0].all_fields != pair[1].all_fields
        changed = {
            key
            for key in pair[0].all_fields
            if pair[0].all_fields[key] != pair[1].all_fields.get(key)
        }
        assert changed == set(pair[0].forbidden_fields)
        assert pair[0].ground_truth == pair[1].ground_truth


def test_stratified_pilot_selection_preserves_complete_pairs(tmp_path: Path) -> None:
    source = tmp_path / "cases.jsonl"
    subset = tmp_path / "pilot.jsonl"
    manifest_path = tmp_path / "pilot_manifest.json"
    generate_dataset(source, cases_per_workflow=10, seed=20260802)

    manifest = select_stratified_cases(
        source, subset, manifest_path, cases_per_workflow=10
    )
    rows = read_jsonl(subset)

    assert manifest["records"] == 40
    assert manifest["pairs"] == 20
    assert set(manifest["counts_by_workflow"].values()) == {10}
    assert len({row["pair_id"] for row in rows}) == 20
    assert all(
        sorted(row["variant"] for row in rows if row["pair_id"] == pair_id)
        == ["A", "B"]
        for pair_id in {row["pair_id"] for row in rows}
    )
