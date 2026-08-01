from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from purposebench.adapters.compex import CompexAdapter
from purposebench.adapters.mock import MockAdapter
from purposebench.adapters.model_api import OpenAICompatibleAdapter
from purposebench.models import BenchmarkCase
from purposebench.prompts import build_chat_payload
from purposebench.utils import (
    append_jsonl,
    docker_image_provenance,
    git_commit,
    git_provenance,
    read_jsonl,
    sha256_file,
    sha256_json,
)


def _load_policy(root: Path, workflow: str) -> dict[str, Any]:
    with (root / "policies" / f"{workflow}.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _adapter(condition: str, forced: str | None = None):
    if forced == "mock":
        return MockAdapter()
    if condition == "compex_purpose_bound":
        return CompexAdapter()
    return OpenAICompatibleAdapter()


def run_experiment(
    root: Path,
    config_path: Path,
    condition_filter: str | None = None,
    limit: int | None = None,
    forced_adapter: str | None = None,
) -> int:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dataset_path = root / config["dataset_path"]
    cases = [BenchmarkCase.model_validate(row) for row in read_jsonl(dataset_path)]
    if limit is not None:
        cases = cases[:limit]
    results_path = root / config["results_path"]
    completed: set[str] = set()
    if config.get("resume", True):
        for row in read_jsonl(results_path):
            if row.get("record_type", "execution") != "execution":
                continue
            if row.get("status") == "ok" or not config.get("retry_failed_on_resume", True):
                completed.add(row.get("dedupe_key", ""))

    dataset_hash = sha256_file(dataset_path)
    config_hash = sha256_json(config)
    current_git_sha = git_commit(root)
    benchmark_provenance = git_provenance(root)
    platform_root = Path(
        os.getenv("COMPEX_PLATFORM_ROOT", str(root.parents[1]))
    ).resolve()
    platform_provenance = git_provenance(platform_root)
    agent_image = os.getenv("COMPEX_AGENT_IMAGE", "purposebound-finance-agent:local")
    agent_image_provenance = docker_image_provenance(agent_image)
    previous_events = read_jsonl(results_path)
    previous_event_hash = next(
        (
            row.get("event_hash")
            for row in reversed(previous_events)
            if row.get("record_type", "execution") == "execution" and row.get("event_hash")
        ),
        None,
    )
    min_interval = float(config.get("rate_limit", {}).get("min_interval_seconds", 0))
    last_call_finished = 0.0

    count = 0
    for condition in config["conditions"]:
        if condition_filter and condition != condition_filter:
            continue
        adapter = _adapter(condition, forced_adapter)
        for model in config["models"]:
            for repetition in range(config.get("repetitions", 1)):
                for case in cases:
                    dedupe = f"{case.case_id}|{condition}|{model['name']}|{repetition}"
                    if dedupe in completed:
                        continue
                    policy = _load_policy(root, case.workflow)
                    visible = (
                        case.allowed_projection()
                        if condition in {"metadata_prefilter", "compex_purpose_bound"}
                        else case.all_fields
                    )
                    intended_request = build_chat_payload(
                        task=case.user_request,
                        visible_data=visible,
                        condition=condition,
                        policy=policy,
                        model=model,
                        seed=int(config["seed"]) + repetition,
                    )
                    since_last = time.monotonic() - last_call_finished
                    if min_interval > 0 and since_last < min_interval:
                        time.sleep(min_interval - since_last)
                    started = datetime.now(UTC)
                    tick = time.perf_counter()
                    result = adapter.execute(
                        case=case,
                        policy=policy,
                        model=model,
                        condition=condition,
                        seed=int(config["seed"]) + repetition,
                    )
                    latency_ms = round((time.perf_counter() - tick) * 1000, 3)
                    last_call_finished = time.monotonic()
                    ended = datetime.now(UTC)
                    record = {
                        "record_type": "execution",
                        "run_id": str(uuid.uuid4()),
                        "dedupe_key": dedupe,
                        "timestamp": started.isoformat(),
                        "experiment_name": config["experiment_name"],
                        "protocol_version": config.get("protocol_version", "unfrozen"),
                        "git_sha": current_git_sha,
                        "git_commit": current_git_sha,
                        "benchmark_repository": benchmark_provenance,
                        "compex_platform_repository": platform_provenance,
                        "container_provenance": (
                            agent_image_provenance
                            if condition == "compex_purpose_bound"
                            else None
                        ),
                        "configuration_hash": config_hash,
                        "dataset_hash": dataset_hash,
                        "case_id": case.case_id,
                        "pair_id": case.pair_id,
                        "workflow": case.workflow,
                        "purpose": case.purpose,
                        "variant": case.variant,
                        "attack_class": case.attack_class,
                        "condition": condition,
                        "model_provider": model.get("provider", "unknown"),
                        "model_name": model["name"],
                        "model_identifier": model["name"],
                        "model_version": result.model_version,
                        "seed": int(config["seed"]) + repetition,
                        "repetition": repetition,
                        "policy_hash": sha256_json(policy),
                        "prompt_hash": sha256_json(intended_request["messages"]),
                        "input_hash": sha256_json(case.all_fields),
                        "authorized_projection_hash": sha256_json(case.allowed_projection()),
                        "started_at": started.isoformat(),
                        "ended_at": ended.isoformat(),
                        "latency_ms": latency_ms,
                        "adapter_latency_ms": result.adapter_latency_ms,
                        "status": result.status,
                        "request": intended_request,
                        "request_payload": {
                            "user_request": case.user_request,
                            "all_fields": case.all_fields,
                            "allowed_fields": case.allowed_fields,
                            "forbidden_fields": case.forbidden_fields,
                            "allowed_actions": policy.get("allowed_actions", []),
                            "output_schema": policy.get("output_schema", {}),
                        },
                        "raw_response": result.raw_response,
                        "parsed_output": result.parsed_output,
                        "tool_calls": result.tool_calls,
                        "accessed_fields": result.accessed_fields,
                        "denied_fields": result.denied_fields,
                        "policy_events": result.policy_events,
                        "output_validation_events": result.output_validation_events,
                        "compex_run_id": result.compex_run_id,
                        "evidence_id": result.evidence_id,
                        "evidence": result.evidence,
                        "token_usage": result.token_usage,
                        "estimated_cost": result.estimated_cost,
                        "attempts": result.attempts,
                        "retry_policy": config.get(
                            "retry_policy",
                            {"max_attempts": 3, "backoff_seconds": [1, 2]},
                        ),
                        "ground_truth": case.ground_truth,
                        "sentinel_values": case.sentinel_values,
                        "error": result.error,
                    }
                    record["output_hash"] = sha256_json(
                        {
                            "raw_response": result.raw_response,
                            "parsed_output": result.parsed_output,
                        }
                    )
                    record["previous_event_hash"] = previous_event_hash
                    record["event_hash"] = sha256_json(record)
                    append_jsonl(results_path, record)
                    previous_event_hash = record["event_hash"]

                    if isinstance(adapter, CompexAdapter) and result.evidence_id:
                        cleanup_events = adapter.cleanup(result.evidence)
                        cleanup_record = {
                            "record_type": "cleanup",
                            "run_id": record["run_id"],
                            "timestamp": datetime.now(UTC).isoformat(),
                            "git_sha": record["git_sha"],
                            "case_id": case.case_id,
                            "compex_run_id": result.compex_run_id,
                            "evidence_id": result.evidence_id,
                            "events": cleanup_events,
                        }
                        cleanup_record["event_hash"] = sha256_json(cleanup_record)
                        append_jsonl(root / "results" / "raw" / "cleanup.jsonl", cleanup_record)
                    count += 1
    return count
