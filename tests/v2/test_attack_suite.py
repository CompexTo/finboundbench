from pathlib import Path

import pytest

from purposebench.v2.attack_suite import ATTACK_DEFINITIONS, validate_attack_definitions


def test_attack_manifest_covers_all_seventeen_required_attacks() -> None:
    assert len(ATTACK_DEFINITIONS) == 17
    assert len({item.attack_id for item in ATTACK_DEFINITIONS}) == 17
    assert all(item.source_references for item in ATTACK_DEFINITIONS)


def test_attack_manifest_rejects_missing_platform_sources(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="attack test sources"):
        validate_attack_definitions(tmp_path)
