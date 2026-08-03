"""Executable manifest for the protocol-v2-local platform attack suite."""

from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from purposebench.utils import git_commit


@dataclass(frozen=True)
class AttackDefinition:
    attack_id: str
    expected_decision: str
    source_references: tuple[str, ...]


ATTACK_DEFINITIONS = (
    AttackDefinition(
        "stale_filter_configuration",
        "DENY",
        (
            "services/api/test/unit/v2/purpose-bound-contracts.service.spec.ts",
            "services/api/test/unit/v2/platform-data-preparation.spec.ts",
        ),
    ),
    AttackDefinition(
        "wrong_endpoint_receiving_full_data",
        "DENY",
        ("services/runner/src/providers/adapters.test.ts",),
    ),
    AttackDefinition(
        "projection_substitution",
        "DENY",
        (
            "services/api/test/unit/v2/platform-data-preparation.spec.ts",
            "services/runner/src/backends/backends.test.ts",
        ),
    ),
    AttackDefinition(
        "dataset_substitution",
        "DENY",
        (
            "services/api/test/unit/v2/platform-data-preparation.spec.ts",
            "services/runner/src/backends/backends.test.ts",
        ),
    ),
    AttackDefinition(
        "model_substitution",
        "DENY",
        (
            "services/runner/src/local-models/ollama-model.test.ts",
            "services/runner/src/providers/adapters.test.ts",
        ),
    ),
    AttackDefinition(
        "prompt_substitution",
        "DENY",
        (
            "services/runner/src/local-models/ollama-model.test.ts",
            "services/runner/src/providers/adapters.test.ts",
        ),
    ),
    AttackDefinition(
        "output_schema_substitution",
        "DENY",
        (
            "services/runner/src/local-models/ollama-model.test.ts",
            "services/runner/src/providers/adapters.test.ts",
        ),
    ),
    AttackDefinition(
        "weakened_dp_settings",
        "DENY",
        (
            "services/api/test/unit/v2/privacy-platform.spec.ts",
            "services/api/test/unit/v2/evidence-v2.spec.ts",
        ),
    ),
    AttackDefinition(
        "privacy_budget_bypass",
        "DENY",
        ("services/api/test/unit/v2/privacy-platform.spec.ts",),
    ),
    AttackDefinition(
        "output_leakage",
        "DENY",
        ("services/api/test/unit/v2/native-output-release.spec.ts",),
    ),
    AttackDefinition(
        "unauthorized_artifact_release",
        "DENY",
        ("services/api/test/unit/v2/native-output-release.spec.ts",),
    ),
    AttackDefinition(
        "unauthorized_egress",
        "DENY",
        ("services/api/test/unit/v2/purpose-capability-enforcer.spec.ts",),
    ),
    AttackDefinition(
        "secret_leakage",
        "DENY_AND_SENTINEL_ABSENT",
        (
            "services/runner/src/secrets/secrets.test.ts",
            "services/runner/src/providers/adapters.test.ts",
        ),
    ),
    AttackDefinition(
        "evidence_tampering",
        "DETECT",
        ("services/api/test/unit/v2/evidence-v2.spec.ts",),
    ),
    AttackDefinition(
        "execution_after_approval_expiry",
        "DENY",
        (
            "services/api/test/unit/confidential-execution-contract.spec.ts",
            "services/runner/src/backends/backends.test.ts",
        ),
    ),
    AttackDefinition(
        "execution_after_revocation",
        "DENY",
        (
            "services/api/test/unit/confidential-execution-contract.spec.ts",
            "services/api/test/unit/v2/lineage.spec.ts",
        ),
    ),
    AttackDefinition(
        "undeclared_tool",
        "DENY",
        ("services/api/test/unit/v2/purpose-capability-enforcer.spec.ts",),
    ),
)


def validate_attack_definitions(platform_root: Path) -> None:
    expected = {
        "stale_filter_configuration",
        "wrong_endpoint_receiving_full_data",
        "projection_substitution",
        "dataset_substitution",
        "model_substitution",
        "prompt_substitution",
        "output_schema_substitution",
        "weakened_dp_settings",
        "privacy_budget_bypass",
        "output_leakage",
        "unauthorized_artifact_release",
        "unauthorized_egress",
        "secret_leakage",
        "evidence_tampering",
        "execution_after_approval_expiry",
        "execution_after_revocation",
        "undeclared_tool",
    }
    actual = {definition.attack_id for definition in ATTACK_DEFINITIONS}
    if actual != expected or len(actual) != len(ATTACK_DEFINITIONS):
        raise RuntimeError("local attack manifest is incomplete or contains duplicates")
    missing = sorted(
        reference
        for definition in ATTACK_DEFINITIONS
        for reference in definition.source_references
        if not (platform_root / reference).is_file()
    )
    if missing:
        raise FileNotFoundError(f"attack test sources are missing: {missing}")


def _run_gate(platform_root: Path, command: str) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f". .\\infra\\scripts\\use-node22.ps1; {command}",
        ],
        cwd=platform_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout = completed.stdout
    stderr = completed.stderr
    return {
        "commandDescription": command,
        "exitCode": completed.returncode,
        "durationSeconds": round(time.perf_counter() - started, 3),
        "stdoutSha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "stderrSha256": hashlib.sha256(stderr.encode()).hexdigest(),
        "stdoutTail": stdout.splitlines()[-20:],
        "stderrTail": stderr.splitlines()[-20:],
    }


def run_local_attack_suite(benchmark_root: Path, platform_root: Path) -> dict[str, Any]:
    """Run the focused platform gates and return a non-claiming raw record."""

    validate_attack_definitions(platform_root)
    api_sources = sorted(
        {
            reference
            for definition in ATTACK_DEFINITIONS
            for reference in definition.source_references
            if reference.startswith("services/api/")
        }
    )
    api_test_paths = [
        str(Path(reference).relative_to("services/api")).replace("\\", "/")
        for reference in api_sources
    ]
    api_command = (
        "pnpm --filter @compex/api test:unit -- --runTestsByPath "
        + " ".join(api_test_paths)
    )
    gates = [
        _run_gate(platform_root, api_command),
        _run_gate(platform_root, "pnpm --filter @compex/runner test"),
    ]
    passed = all(gate["exitCode"] == 0 for gate in gates)
    return {
        "schemaVersion": "purposebound-finance.local-attack-suite.v2",
        "recordedAt": datetime.now(UTC).isoformat(),
        "status": "passed" if passed else "failed",
        "benchmarkCommit": git_commit(benchmark_root),
        "platformCommit": git_commit(platform_root),
        "attacks": [asdict(definition) for definition in ATTACK_DEFINITIONS],
        "gates": gates,
        "excludedThreats": [
            {
                "threat": "malicious_host_root_or_administrator",
                "reason": (
                    "Outside the trusted-host local threat model; reserved for a future "
                    "hardware-attested AWS Nitro backend."
                ),
            }
        ],
    }
