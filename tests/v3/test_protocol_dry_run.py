from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from purposebench.v3.attacks import (
    ATTACK_REGISTRY,
    execute_test_double_attack,
)
from purposebench.v3.dry_run import (
    build_development_pairs,
    run_no_cost_dry_run,
    validate_development_pairs,
    verify_event_chain,
)
from purposebench.v3.protocol import (
    EXPECTED_CONDITIONS,
    GIT_COMMIT_PATTERN,
    validate_dry_run_config,
    validate_protocol_design,
)

ROOT = Path(__file__).parents[2]
PLATFORM_ROOT = ROOT.parents[1]


def test_protocol_and_dry_run_configs_are_complete_and_no_cost() -> None:
    protocol = validate_protocol_design(ROOT)
    config = validate_dry_run_config(ROOT)

    assert tuple(condition["id"] for condition in protocol["conditions"]) == (
        EXPECTED_CONDITIONS
    )
    assert len(ATTACK_REGISTRY) == 57
    assert config["provider_calls_permitted"] == 0
    assert config["paid_secrets_permitted"] is False
    assert config["hardware_attestation"] is False
    assert len(config["test_double_models"]) == 3
    assert config["repetitions"] == 3


def test_git_commit_validator_accepts_the_repository_object_format() -> None:
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    assert len(commit) == 40
    assert GIT_COMMIT_PATTERN.fullmatch(commit)
    assert GIT_COMMIT_PATTERN.fullmatch("a" * 64)


def test_development_pairs_pass_sensitivity_and_invariance_gates() -> None:
    config = validate_dry_run_config(ROOT)
    records = build_development_pairs(ROOT, config)
    validation = validate_development_pairs(records, config)

    assert validation["pairs"] == 40
    assert validation["records"] == 80
    assert 0.55 <= validation["publicAccuracy"] <= 0.85
    assert validation["oracleGain"] >= 0.08
    assert validation["taskBPairInvariant"] is True


def test_attack_oracle_exercises_both_prevention_and_silent_compromise() -> None:
    outcomes = {
        execute_test_double_attack(attack, condition)
        for attack in ATTACK_REGISTRY
        for condition in attack.applicable_conditions
    }
    assert outcomes == {"PREVENTED", "SUCCEEDED_DETECTED", "SILENT_COMPROMISE"}


def test_complete_dry_run_is_deterministic_and_never_populates_paper_results(
    tmp_path: Path,
) -> None:
    first = run_no_cost_dry_run(
        ROOT,
        PLATFORM_ROOT,
        output_dir=tmp_path / "first",
        require_freeze=False,
    )
    second = run_no_cost_dry_run(
        ROOT,
        PLATFORM_ROOT,
        output_dir=tmp_path / "second",
        require_freeze=False,
    )
    assert first["eventCounts"] == {
        "inferenceBatches": 504,
        "attackAttempts": 705,
        "privacyTestDoubleRuns": 12,
        "total": 1221,
    }
    assert first["providerCalls"] == 0
    assert first["paidCostEur"] == 0
    assert first["paidSecretRead"] is False
    assert first["awsActions"] == 0
    assert first["hardwareAttestation"] is False
    assert first["researchClaimsPermitted"] is False
    assert first["files"] == second["files"]
    report = json.loads(
        (tmp_path / "first/derived/instrumentation-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["status"] == "PASSED_INSTRUMENTATION_ONLY"
    assert report["attacks"]["registeredAttackIds"] == 57
    assert report["privacy"]["measurementType"] == "TEST_DOUBLE_NOT_DP_TRAINING"
    assert "intentionally withheld" in (
        ROOT / "paper/generated/results_placeholder.tex"
    ).read_text(encoding="utf-8")


def test_event_chain_detects_tampering(tmp_path: Path) -> None:
    run_no_cost_dry_run(
        ROOT,
        PLATFORM_ROOT,
        output_dir=tmp_path / "run",
        require_freeze=False,
    )
    events_path = tmp_path / "run/raw/events.jsonl"
    rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    assert verify_event_chain(rows)
    rows[10]["payload"]["providerCalls"] = 1
    assert not verify_event_chain(rows)


def test_existing_dry_run_output_is_never_overwritten(tmp_path: Path) -> None:
    output = tmp_path / "occupied"
    output.mkdir()
    (output / "sentinel.txt").write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        run_no_cost_dry_run(
            ROOT,
            PLATFORM_ROOT,
            output_dir=output,
            require_freeze=False,
        )
