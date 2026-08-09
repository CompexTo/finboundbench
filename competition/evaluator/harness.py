"""Submission runners for the FinBoundBench harness.

Three submission kinds:
- python module: a module exposing ``decide(payload: dict) -> dict``
- python callable: any object with ``__call__(payload) -> dict``
- docker container: an HTTP endpoint ``POST /decide`` receiving the payload
  and returning ``{"action": ...}`` (used in the final evaluation; the local
  harness supports it through ``--docker-base-url``)

A response is ``{"action": <one of payload["actions"]>, "cost_usd": <float
optional>, "evidence": <optional dict>}``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any


class PythonSubmission:
    def __init__(self, callable_obj: Callable[[dict[str, Any]], dict[str, Any]], name: str):
        self._fn = callable_obj
        self.name = name

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._fn(payload)


def load_python_submission(module_path: str, name: str = "submission") -> PythonSubmission:
    path = Path(module_path).resolve()
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load submission module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "decide"):
        raise ImportError(f"{path} must define decide(payload) -> dict")
    return PythonSubmission(module.decide, name)


class DockerSubmission:
    def __init__(self, base_url: str, name: str = "docker-submission"):
        self.base_url = base_url.rstrip("/")
        self.name = name

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/decide",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))


def run_submission(
    submission: Any,
    requests: dict[str, dict[str, Any]],
    inject_labels_for: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Run a submission over rendered requests.

    Returns decisions[request_id] = {"response": ..., "actions": [...], "label": ...}.

    If ``inject_labels_for`` equals submission.name, the ground-truth label is
    added to the payload under ``_ground_truth`` (dev-only oracle support).
    """
    decisions: dict[str, dict[str, Any]] = {}
    for request_id, payload in requests.items():
        if inject_labels_for is not None and submission.name == inject_labels_for:
            payload = dict(payload)
            payload["_ground_truth"] = payload["label"]
        try:
            response = submission.decide(payload)
        except Exception as exc:  # noqa: BLE001 - a failing submission must be scored, not crash the run
            response = {"action": None, "error": str(exc), "cost_usd": 0.0}
        if not isinstance(response, dict):
            response = {"action": None, "error": "non-dict response", "cost_usd": 0.0}
        decisions[request_id] = {
            "response": response,
            "actions": payload["actions"],
            "label": payload["label"],
        }
    return decisions
