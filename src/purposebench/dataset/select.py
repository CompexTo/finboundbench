from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from purposebench.models import BenchmarkCase
from purposebench.utils import read_jsonl, sha256_file


def select_stratified_cases(
    source: Path,
    destination: Path,
    manifest_path: Path,
    cases_per_workflow: int = 10,
) -> dict[str, Any]:
    """Select complete pairs, balanced across workflows and attack classes."""
    if cases_per_workflow < 2 or cases_per_workflow % 2:
        raise ValueError("cases_per_workflow must be a positive even number")
    cases = [BenchmarkCase.model_validate(row) for row in read_jsonl(source)]
    pairs_by_workflow: dict[str, dict[str, list[BenchmarkCase]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for case in cases:
        pairs_by_workflow[case.workflow][case.pair_id].append(case)

    selected: list[BenchmarkCase] = []
    pairs_needed = cases_per_workflow // 2
    for workflow in sorted(pairs_by_workflow):
        complete_pairs = [
            pair
            for pair in pairs_by_workflow[workflow].values()
            if sorted(case.variant for case in pair) == ["A", "B"]
        ]
        attack_buckets: dict[str, list[list[BenchmarkCase]]] = defaultdict(list)
        for pair in complete_pairs:
            attack_buckets[pair[0].attack_class].append(pair)
        chosen: list[list[BenchmarkCase]] = []
        while len(chosen) < pairs_needed:
            progressed = False
            for attack_class in sorted(attack_buckets):
                if attack_buckets[attack_class] and len(chosen) < pairs_needed:
                    chosen.append(attack_buckets[attack_class].pop(0))
                    progressed = True
            if not progressed:
                raise ValueError(f"not enough complete pairs for workflow {workflow}")
        for pair in chosen:
            selected.extend(sorted(pair, key=lambda case: case.variant))

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        for case in selected:
            handle.write(
                json.dumps(
                    case.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )

    workflow_counts = Counter(case.workflow for case in selected)
    attack_counts = Counter(
        f"{case.workflow}:{case.attack_class}" for case in selected
    )
    manifest = {
        "source": str(source),
        "destination": str(destination),
        "source_sha256": sha256_file(source),
        "subset_sha256": sha256_file(destination),
        "records": len(selected),
        "pairs": len(selected) // 2,
        "cases_per_workflow": cases_per_workflow,
        "counts_by_workflow": dict(sorted(workflow_counts.items())),
        "counts_by_workflow_and_attack": dict(sorted(attack_counts.items())),
        "pair_ids": sorted({case.pair_id for case in selected}),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
