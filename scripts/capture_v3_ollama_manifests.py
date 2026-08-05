"""Capture exact installed Ollama manifests without downloading model data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from purposebench.utils import sha256_json


def _api_json(path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:11434{path}",
        data=data,
        headers={"content-type": "application/json"},
        method="GET" if data is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise TypeError("Ollama API response must be a JSON object")
    return value


def _engine_version() -> str:
    output = subprocess.check_output(["ollama", "--version"], text=True).strip()
    prefix = "ollama version is "
    if not output.startswith(prefix):
        raise ValueError("unexpected Ollama version output")
    return output.removeprefix(prefix)


def _manifest_path(model: str) -> Path:
    model_root = Path(
        os.environ.get("OLLAMA_MODELS", str(Path.home() / ".ollama/models"))
    )
    name, separator, tag = model.partition(":")
    if not separator or not name or not tag:
        raise ValueError("model must be an exact name:tag reference")
    return model_root / "manifests/registry.ollama.ai/library" / name / tag


def capture(
    model: str,
    *,
    captured_at: str,
    hardware: dict[str, Any],
) -> dict[str, Any]:
    tags = _api_json("/api/tags").get("models", [])
    matches = [item for item in tags if item.get("name") == model and item.get("model") == model]
    if len(matches) != 1:
        raise ValueError(f"installed model tag is not unique: {model}")
    installed = matches[0]
    digest = str(installed.get("digest", "")).removeprefix("sha256:")
    if len(digest) != 64:
        raise ValueError(f"installed model digest is invalid: {model}")
    show = _api_json("/api/show", {"model": model, "verbose": False})
    details = show.get("details", {})
    model_info = show.get("model_info", {})
    architecture = model_info.get("general.architecture")
    parameter_count = model_info.get("general.parameter_count")
    context_size = model_info.get(f"{architecture}.context_length")
    if not isinstance(parameter_count, int) or not isinstance(context_size, int):
        raise TypeError(f"model metadata is incomplete: {model}")
    local_manifest_path = _manifest_path(model)
    local_manifest_bytes = local_manifest_path.read_bytes()
    if hashlib.sha256(local_manifest_bytes).hexdigest() != digest:
        raise ValueError(f"local registry manifest digest differs from /api/tags: {model}")
    local_manifest = json.loads(local_manifest_bytes)
    layer_values = [local_manifest["config"], *local_manifest["layers"]]
    layers = [
        {
            "mediaType": layer["mediaType"],
            "digest": layer["digest"],
            "sizeBytes": layer["size"],
        }
        for layer in layer_values
    ]
    core = {
        "schema": "compex-ollama-model-manifest-v2",
        "modelTag": model,
        "pinnedModelId": f"{model}@sha256:{digest}",
        "manifestDigest": f"sha256:{digest}",
        "modelRevision": f"sha256:{digest}",
        "parameterCount": parameter_count,
        "parameterSize": details["parameter_size"],
        "quantization": details["quantization_level"],
        "format": details["format"],
        "contextSize": context_size,
        "inferenceEngine": "OLLAMA",
        "inferenceEngineVersion": _engine_version(),
        "downloadSource": f"registry.ollama.ai/library/{model}",
        "layers": layers,
        "capabilities": show.get("capabilities", []),
        "hardware": hardware,
        "capturedAt": captured_at,
    }
    return {**core, "manifestHash": sha256_json(core)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--captured-at", required=True)
    parser.add_argument("--hardware-from", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.hardware_from.read_text(encoding="utf-8"))
    hardware = source["hardware"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for model in args.model:
        output = args.output_dir / f"{model.replace(':', '-')}.json"
        if output.exists():
            raise FileExistsError(f"manifest already exists: {output}")
        manifest = capture(model, captured_at=args.captured_at, hardware=hardware)
        output.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"{model} {manifest['manifestHash']} {output}")


if __name__ == "__main__":
    main()
