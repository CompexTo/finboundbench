from pathlib import Path

from purposebench.dataset.generate import generate_dataset
from purposebench.models import BenchmarkCase
from purposebench.utils import read_jsonl


def test_pairs_share_allowed_projection(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    generate_dataset(path, cases_per_workflow=2, seed=123)
    cases = [BenchmarkCase.model_validate(row) for row in read_jsonl(path)]
    pairs = {}
    for case in cases:
        pairs.setdefault(case.pair_id, []).append(case)
    for pair in pairs.values():
        assert len(pair) == 2
        assert pair[0].allowed_projection() == pair[1].allowed_projection()
        assert pair[0].all_fields != pair[1].all_fields
