"""Tests for the v3 OpenRouter R0 admission gate (no paid calls)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from purposebench.utils import sha256_json
from purposebench.v3.remote_admission import (
    ADMISSION_LABEL,
    BRIDGE_PATH,
    RESEARCH_ARTIFACTS,
    build_bridge_payload,
    build_remote_admission_freeze,
    native_release_policy,
    validate_remote_admission_config,
)

ROOT = Path(__file__).parents[2]
PLATFORM_ROOT = ROOT.parents[1]


def _load_config() -> dict[str, Any]:
    import yaml
    return yaml.safe_load((ROOT / "configs/v3/openrouter-model-admission-v3.yaml").read_text(encoding="utf-8"))


def test_validate_remote_admission_config_accepts_the_current_config() -> None:
    config = _load_config()
    validate_remote_admission_config(ROOT, config)


def test_validate_remote_admission_config_rejects_wrong_schema_version() -> None:
    config = _load_config()
    config["schema_version"] = "wrong"
    with pytest.raises(ValueError, match="unsafe or invalid"):
        validate_remote_admission_config(ROOT, config)


def test_validate_remote_admission_config_rejects_paid_secrets_disabled() -> None:
    config = _load_config()
    config["paid_secrets_permitted"] = False
    with pytest.raises(ValueError, match="unsafe or invalid"):
        validate_remote_admission_config(ROOT, config)


def test_validate_remote_admission_config_rejects_confirmatory_claims_enabled() -> None:
    config = _load_config()
    config["confirmatory_claims_permitted"] = True
    with pytest.raises(ValueError, match="unsafe or invalid"):
        validate_remote_admission_config(ROOT, config)


def test_validate_remote_admission_config_rejects_retries() -> None:
    config = _load_config()
    config["automatic_retries"] = 1
    with pytest.raises(ValueError, match="unsafe or invalid"):
        validate_remote_admission_config(ROOT, config)


def test_validate_remote_admission_config_rejects_fallback() -> None:
    config = _load_config()
    config["fallback_permitted"] = True
    with pytest.raises(ValueError, match="unsafe or invalid"):
        validate_remote_admission_config(ROOT, config)


def test_validate_remote_admission_config_rejects_budget_exceeding_authorization() -> None:
    config = _load_config()
    config["budget"]["absolute_authorized_eur"] = 100.0
    with pytest.raises(ValueError, match="budget envelope"):
        validate_remote_admission_config(ROOT, config)


def test_validate_remote_admission_config_rejects_duplicate_lane_ids() -> None:
    config = _load_config()
    config["models"][1]["lane_id"] = config["models"][0]["lane_id"]
    with pytest.raises(ValueError, match="unique"):
        validate_remote_admission_config(ROOT, config)


def test_validate_remote_admission_config_rejects_missing_manifest_file() -> None:
    config = _load_config()
    config["models"][0]["manifest_path"] = "docs/v3/model-manifests/nonexistent.json"
    with pytest.raises((ValueError, FileNotFoundError)):
        validate_remote_admission_config(ROOT, config)


def test_validate_remote_admission_config_rejects_manifest_hash_mismatch() -> None:
    config = _load_config()
    config["models"][0]["expected_manifest_hash"] = "0" * 64
    with pytest.raises(ValueError, match="manifest hash"):
        validate_remote_admission_config(ROOT, config)


def test_validate_remote_admission_config_rejects_manifest_path_escape() -> None:
    config = _load_config()
    config["models"][0]["manifest_path"] = "../../etc/passwd"
    with pytest.raises(ValueError, match="escaped"):
        validate_remote_admission_config(ROOT, config)


def test_build_bridge_payload_matches_config() -> None:
    config = _load_config()
    model = config["models"][0]
    payload = build_bridge_payload(config, model)
    assert payload["contractHash"]
    assert payload["workloadImageDigest"] == config["workload_image_digest"]
    assert payload["selectedFields"] == config["selected_fields"]
    assert payload["records"] == config["records"]
    assert payload["prompts"] == config["prompts"]
    assert payload["responseSchema"] == config["response_schema"]
    assert payload["outputTokenLimit"] == config["output_token_limit"]
    assert payload["timeoutMs"] == config["timeout_ms"]


def test_build_bridge_payload_contract_hash_is_deterministic() -> None:
    config = _load_config()
    model = config["models"][0]
    first = build_bridge_payload(config, model)
    second = build_bridge_payload(config, model)
    assert first["contractHash"] == second["contractHash"]


def test_build_bridge_payload_varies_by_model() -> None:
    config = _load_config()
    model_a = config["models"][0]
    model_b = config["models"][1]
    payload_a = build_bridge_payload(config, model_a)
    payload_b = build_bridge_payload(config, model_b)
    assert payload_a["contractHash"] != payload_b["contractHash"]


def test_native_release_policy_has_all_required_validators() -> None:
    config = _load_config()
    policy = native_release_policy(config)
    assert policy["policyRuleId"] == "finboundbench-v3-r0-admission-release"
    assert len(policy["requiredValidators"]) == 10
    assert policy["requiredFields"] == {"paths": ["/decision", "/score", "/reason"]}
    assert policy["decisionVocabulary"]["permittedValues"] == ["STANDARD_QUEUE", "PRIORITY_QUEUE"]
    assert policy["numericBounds"]["bounds"][0]["minimum"] == 0
    assert policy["numericBounds"]["bounds"][0]["maximum"] == 100


def test_native_release_policy_rejects_prohibited_values() -> None:
    config = _load_config()
    policy = native_release_policy(config)
    assert "SYNTHETIC_INTERNAL_LOW" in policy["prohibitedExactValues"]["values"]
    assert "SYNTHETIC_INTERNAL_HIGH" in policy["prohibitedExactValues"]["values"]


def test_build_remote_admission_freeze_produces_valid_hash() -> None:
    config = _load_config()
    research_commit = "a" * 40
    platform_commit = "b" * 40
    freeze = build_remote_admission_freeze(
        ROOT,
        PLATFORM_ROOT,
        research_commit=research_commit,
        platform_commit=platform_commit,
    )
    claimed = freeze.pop("freezeManifestHash")
    assert sha256_json(freeze) == claimed
    freeze["freezeManifestHash"] = claimed
    assert freeze["status"] == "FROZEN_R0_ADMISSION_ONLY"
    assert freeze["remoteProviderCallsPermitted"] == config["remote_provider_calls_permitted"]
    assert len(freeze["modelManifestHashes"]) == len(config["models"])
    assert len(freeze["artifacts"]) >= len(RESEARCH_ARTIFACTS)


def test_build_remote_admission_freeze_includes_all_research_artifacts() -> None:
    freeze = build_remote_admission_freeze(
        ROOT,
        PLATFORM_ROOT,
        research_commit="a" * 40,
        platform_commit="b" * 40,
    )
    research_paths = {a["path"] for a in freeze["artifacts"] if a["repository"] == "research"}
    for artifact in RESEARCH_ARTIFACTS:
        assert artifact.as_posix() in research_paths


def test_build_remote_admission_freeze_includes_all_model_manifests() -> None:
    config = _load_config()
    freeze = build_remote_admission_freeze(
        ROOT,
        PLATFORM_ROOT,
        research_commit="a" * 40,
        platform_commit="b" * 40,
    )
    manifest_paths = {a["path"] for a in freeze["artifacts"] if a["repository"] == "research"}
    for model in config["models"]:
        assert model["manifest_path"] in manifest_paths


def test_build_remote_admission_freeze_includes_platform_artifacts() -> None:
    freeze = build_remote_admission_freeze(
        ROOT,
        PLATFORM_ROOT,
        research_commit="a" * 40,
        platform_commit="b" * 40,
    )
    platform_artifacts = [a for a in freeze["artifacts"] if a["repository"] == "platform"]
    assert len(platform_artifacts) == 4


def test_build_remote_admission_freeze_is_structurally_stable() -> None:
    freeze_a = build_remote_admission_freeze(
        ROOT, PLATFORM_ROOT, research_commit="a" * 40, platform_commit="b" * 40
    )
    freeze_b = build_remote_admission_freeze(
        ROOT, PLATFORM_ROOT, research_commit="a" * 40, platform_commit="b" * 40
    )
    assert freeze_a.keys() == freeze_b.keys()
    assert freeze_a["status"] == freeze_b["status"]
    assert freeze_a["remoteProviderCallsPermitted"] == freeze_b["remoteProviderCallsPermitted"]
    assert freeze_a["modelManifestHashes"] == freeze_b["modelManifestHashes"]
    assert freeze_a["repositoryBindings"] == freeze_b["repositoryBindings"]
    assert len(freeze_a["artifacts"]) == len(freeze_b["artifacts"])


def test_admission_config_model_count_matches_lane_ids() -> None:
    config = _load_config()
    assert len(config["models"]) == config["remote_provider_calls_permitted"]
    lane_ids = [m["lane_id"] for m in config["models"]]
    assert len(set(lane_ids)) == len(lane_ids)


def test_admission_config_manifest_hashes_are_64_hex() -> None:
    config = _load_config()
    for model in config["models"]:
        h = model["expected_manifest_hash"]
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


def test_admission_config_budget_caps_are_ordered() -> None:
    config = _load_config()
    budget = config["budget"]
    reservation = float(budget["reservation_per_call_eur"])
    phase = float(budget["phase_authorized_eur"])
    absolute = float(budget["absolute_authorized_eur"])
    assert 0 < reservation <= phase <= absolute <= 1.0


def test_admission_config_claude_excluded() -> None:
    config = _load_config()
    claude = config.get("claude_lane")
    assert isinstance(claude, dict)
    assert claude.get("admission") == "EXCLUDED_FROM_R0"


def test_admission_config_selected_fields_are_unique() -> None:
    config = _load_config()
    fields = config["selected_fields"]
    assert len(fields) == len(set(fields))
    assert len(fields) > 0


def test_admission_config_denied_fields_do_not_overlap_selected() -> None:
    config = _load_config()
    assert set(config["selected_fields"]).isdisjoint(config["denied_fields"])


def test_admission_config_prohibited_values_not_in_records() -> None:
    config = _load_config()
    projected = json.dumps(config["records"], sort_keys=True)
    for value in config.get("prohibited_exact_values", []):
        assert str(value) not in projected
