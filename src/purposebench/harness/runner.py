from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from purposebench.adapters.compex import CompexAdapter
from purposebench.adapters.mock import MockAdapter
from purposebench.adapters.model_api import OpenAICompatibleAdapter
from purposebench.models import BenchmarkCase
from purposebench.utils import append_jsonl, git_commit, read_jsonl, sha256_json, sha256_text


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
    cases = [BenchmarkCase.model_validate(row) for row in read_jsonl(root / config["dataset_path"])]
    if limit is not None:
        cases = cases[:limit]
    results_path = root / config["results_path"]
    completed: set[str] = set()
    if config.get("resume", True):
        for row in read_jsonl(results_path):
            completed.add(row.get("dedupe_key", ""))

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
                    started = datetime.now(timezone.utc)
                    tick = time.perf_counter()
                    result = adapter.execute(
                        case=case,
                        policy=policy,
                        model=model,
                        condition=condition,
                        seed=int(config["seed"]) + repetition,
                    )
                    latency_ms = round((time.perf_counter() - tick) * 1000, 3)
                    ended = datetime.now(timezone.utc)
                    record = {
                        "run_id": str(uuid.uuid4()),
                        "dedupe_key": dedupe,
                        "experiment_name": config["experiment_name"],
                        "git_commit": git_commit(root),
                        "case_id": case.case_id,
                        "pair_id": case.pair_id,
                        "workflow": case.workflow,
                        "purpose": case.purpose,
                        "variant": case.variant,
                        "attack_class": case.attack_class,
                        "condition": condition,
                        "model_provider": model.get("provider", "unknown"),
                        "model_name": model["name"],
                        "seed": int(config["seed"]) + repetition,
                        "repetition": repetition,
                        "policy_hash": sha256_json(policy),
                        "prompt_hash": sha256_text(case.user_request),
                        "input_hash": sha256_json(case.all_fields),
                        "authorized_projection_hash": sha256_json(case.allowed_projection()),
                        "started_at": started.isoformat(),
                        "ended_at": ended.isoformat(),
                        "latency_ms": latency_ms,
                        "status": result.status,
                        "request_payload": {
                            "user_request": case.user_request,
                            "all_fields": case.all_fields,
                            "allowed_fields": case.allowed_fields,
                            "forbidden_fields": case.forbidden_fields,
                        },
                        "raw_response": result.raw_response,
                        "parsed_output": result.parsed_output,
                        "tool_calls": result.tool_calls,
                        "accessed_fields": result.accessed_fields,
                        "policy_events": result.policy_events,
                        "evidence": result.evidence,
                        "token_usage": result.token_usage,
                        "estimated_cost": result.estimated_cost,
                        "ground_truth": case.ground_truth,
                        "sentinel_values": case.sentinel_values,
                        "error": result.error,
                    }
                    append_jsonl(results_path, record)
                    count += 1
    return count
