"""Run the Gate 1 contract through a local fake OpenRouter transport."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from purposebench.utils import git_commit, sha256_file, sha256_json
from purposebench.v2.claude_compatibility import (
    assessment_prompts,
    assessment_schema,
    build_contract_material,
    load_phase_configuration,
)
from purposebench.v2.inference_pilot import load_paired_records, native_release_policy
from purposebench.v2.remote_pilot import _node_binary, prepare_remote_batch


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    platform_root = Path(os.environ["COMPEX_PLATFORM_ROOT"]).resolve()
    config = load_phase_configuration(
        root,
        root / "configs/v2/openrouter-phase2.json",
    )
    dataset_path = root / config["dataset"]
    rows = load_paired_records(dataset_path, pair_limit=1)[:1]
    records, selected_fields, denied_fields, _ = prepare_remote_batch(
        rows,
        dataset_sha256=sha256_file(dataset_path),
    )
    schema = assessment_schema(1, config["actionPolicyValue"])
    prompts = assessment_prompts()
    contract = build_contract_material(
        config=config,
        rows=rows,
        selected_fields=selected_fields,
        denied_fields=denied_fields,
        schema=schema,
        prompts=prompts,
        gate=1,
        platform_commit=git_commit(platform_root),
        bridge_sha256=sha256_file(root / "scripts/governed_openrouter_bridge.cjs"),
    )
    payload = {
        "contractHash": sha256_json(contract),
        "modelManifest": config["modelManifestValue"],
        "workloadImageDigest": "sha256:" + "0" * 64,
        "seed": None,
        "outputTokenLimit": config["claudeCompatibility"]["outputTokenLimit"],
        "timeoutMs": config["claudeCompatibility"]["timeoutMs"],
        "selectedFields": list(selected_fields),
        "records": records,
        "prompts": prompts,
        "responseSchema": schema,
        "nativeReleasePolicy": native_release_policy(schema, rows),
        "actionPolicy": config["actionPolicyValue"],
        "actionPolicyHash": config["actionPolicyHash"],
        "expectedRecordCount": 1,
        "maximumAuthorizedCostEur": config["claudeCompatibility"][
            "maximumReservationPerAttemptEur"
        ],
    }
    environment = os.environ.copy()
    environment["COMPEX_PLATFORM_ROOT"] = str(platform_root)
    completed = subprocess.run(
        [_node_binary(), str(root / "scripts/probe_openrouter_bridge.cjs")],
        input=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "local fake contract probe failed")
    result = json.loads(completed.stdout)
    result["contractHash"] = payload["contractHash"]
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
