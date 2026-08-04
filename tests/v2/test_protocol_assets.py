from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from purposebench.utils import canonical_json, sha256_file
from purposebench.v2.datasets import (
    SourceArtifactManifest,
    TransformationManifest,
    validate_augmented_pairs,
)

ROOT = Path(__file__).parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict)
    return value


def _root_path(value: str) -> Path:
    path = Path(value)
    assert not path.is_absolute()
    assert ".." not in path.parts
    resolved = ROOT / path
    assert resolved.is_file(), value
    return resolved


def test_protocol_v2_dataset_and_model_references_are_self_contained() -> None:
    with (ROOT / "configs/v2/protocol-v2-local.yaml").open("r", encoding="utf-8") as handle:
        protocol = yaml.safe_load(handle)

    assert protocol["protocol_id"] == "protocol-v2-local"
    assert protocol["evidence_schema"] == "compex-evidence-v2"
    assert protocol["freeze"]["status"] == "NOT_FROZEN"
    _root_path(protocol["freeze"]["readiness_document"])

    for dataset in protocol["official_datasets"].values():
        assert dataset["readiness"] == "READY"
        source = SourceArtifactManifest.model_validate(
            _load_json(_root_path(dataset["source_manifest"]))
        )
        transformation = TransformationManifest.model_validate(
            _load_json(_root_path(dataset["transformation_manifest"]))
        )
        paired_path = _root_path(dataset["paired_asset"])
        assert transformation.source_sha256 == source.source_sha256
        assert transformation.transformed_sha256 == sha256_file(paired_path)
        records = [
            json.loads(line)
            for line in paired_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        assert validate_augmented_pairs(records) == transformation.pair_validation

    for model in protocol["local_models"].values():
        manifest = _load_json(_root_path(model["manifest"]))
        assert manifest["modelTag"] == model["tag"]
        assert manifest["pinnedModelId"] == model["immutable_id"]
        claimed_hash = manifest.pop("manifestHash")
        actual_hash = hashlib.sha256(canonical_json(manifest).encode("utf-8")).hexdigest()
        assert claimed_hash == actual_hash

    _root_path(protocol["remote_models"]["manifest"])
    _root_path(protocol["remote_models"]["matrix_config"])
