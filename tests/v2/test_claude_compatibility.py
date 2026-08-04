import json
from pathlib import Path

from purposebench.utils import sha256_json
from purposebench.v2.claude_compatibility import (
    _effective_phase2_provider_calls,
    _gate_artifact_stem,
    _passed_gate_manifest,
    _safe_provider_failure,
    assessment_schema,
    load_phase_configuration,
    repeated_failed_combination,
)


def test_reconciled_pretransport_failure_preserves_first_provider_attempt(
    tmp_path: Path,
) -> None:
    raw = tmp_path / "results/v2/raw/inference"
    raw.mkdir(parents=True)
    artifact = raw / "openrouter-phase2-claude-gate1.jsonl.partial"
    rows = [
        {
            "recordType": "claude_compatibility_gate",
            "evidenceId": "failure-1",
            "status": "failed",
            "gate": 1,
            "providerCalls": 1,
        },
        {
            "recordType": "evidence_correction",
            "originalEvidenceId": "failure-1",
            "correctedProviderCalls": 0,
        },
    ]
    artifact.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    assert _effective_phase2_provider_calls(tmp_path) == 0
    assert _gate_artifact_stem(tmp_path, 1) == (
        "openrouter-phase2-claude-gate1-provider-attempt1",
        1,
    )


def test_gate_manifest_discovery_ignores_reconciliation(tmp_path: Path) -> None:
    manifests = tmp_path / "results/v2/manifests"
    manifests.mkdir(parents=True)
    (manifests / "openrouter-phase2-claude-gate1-pretransport-reconciliation.json").write_text(
        json.dumps({"status": "RECONCILED", "gate": 1}),
        encoding="utf-8",
    )
    assert _passed_gate_manifest(tmp_path, 1) is None
    passing = manifests / "openrouter-phase2-claude-gate1-provider-attempt1.json"
    passing.write_text(
        json.dumps(
            {
                "schemaVersion": "purposebound-finance.claude-compatibility-manifest.v2",
                "status": "PASSED",
                "gate": 1,
            }
        ),
        encoding="utf-8",
    )
    assert _passed_gate_manifest(tmp_path, 1) == passing


def test_phase_configuration_binds_budget_metadata_and_action_policy() -> None:
    root = Path.cwd()
    config = load_phase_configuration(
        root,
        root / "configs/v2/openrouter-phase2.json",
    )
    assert config["budget"]["additionalAuthorizedEur"] == 5.0
    assert config["budget"]["absoluteAuthorizedEur"] == 12.90239384
    assert config["claudeCompatibility"]["maximumCompatibilityBudgetEur"] == 1.5
    assert config["modelManifestValue"]["modelId"] == "anthropic/claude-opus-5"
    assert config["modelManifestValue"]["upstreamRoute"] == "amazon-bedrock"
    assert config["actionPolicyHash"] == sha256_json(config["actionPolicyValue"])


def test_assessment_schema_denies_model_selected_governed_action() -> None:
    binding = json.loads(
        Path("configs/v2/openrouter-action-policy.json").read_text(encoding="utf-8")
    )
    schema = assessment_schema(8, binding["policy"])
    item = schema["properties"]["results"]["items"]
    assert item["additionalProperties"] is False
    assert "governed_action" not in item["properties"]
    assert item["properties"]["normalized_risk_score"] == {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
    }
    assert schema["properties"]["results"]["minItems"] == 8


def test_repeat_guard_and_safe_provider_diagnostic() -> None:
    root = Path.cwd()
    assert repeated_failed_combination(root, "missing", "missing") is False
    manifest = {"upstreamRoute": "amazon-bedrock"}
    diagnostic = {
        "httpStatus": 400,
        "requestId": "request-1",
        "category": "INVALID_STRUCTURED_OUTPUT",
        "providerCode": "invalid_parameter",
        "fieldHints": ["response_format"],
        "selectedProviderRoute": "amazon-bedrock",
        "responseBodySha256": "a" * 64,
    }
    error = RuntimeError(f"bridge failed PROVIDER_SAFE_ERROR:{json.dumps(diagnostic)}")
    assert _safe_provider_failure(error, manifest) == diagnostic
    unsafe = RuntimeError("provider said request secret value")
    fallback = _safe_provider_failure(unsafe, manifest)
    assert fallback["category"] == "UNKNOWN_SAFE_CLASS"
    assert "request secret value" not in json.dumps(fallback)
