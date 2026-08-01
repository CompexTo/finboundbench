from __future__ import annotations

import os
import shutil
import subprocess
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()


def check(name: str, ok: bool, detail: str = "") -> bool:
    mark = "OK" if ok else "FAIL"
    print(f"[{mark}] {name} {detail}")
    return ok


def main() -> int:
    all_ok = True
    all_ok &= check("Python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0])
    base = os.getenv("COMPEX_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
    health = os.getenv("COMPEX_HEALTH_PATH", "/health")
    if os.getenv("COMPEX_MODE", "http") == "http":
        try:
            response = httpx.get(f"{base}{health}", timeout=5)
            all_ok &= check("Compex health", response.is_success, f"HTTP {response.status_code}")
        except httpx.HTTPError as exc:
            all_ok &= check("Compex health", False, str(exc))
    else:
        all_ok &= check("Mapped Compex HTTP mode", False, "only COMPEX_MODE=http is supported")
    all_ok &= check("Compex organization configured", bool(os.getenv("COMPEX_ORG_ID")))
    all_ok &= check("Compex workspace configured", bool(os.getenv("COMPEX_WORKSPACE_ID")))
    api_key = os.getenv("COMPEX_API_KEY", "")
    all_ok &= check("Compex scoped API key configured", api_key.startswith("ck_"))
    all_ok &= check("Docker CLI available", shutil.which("docker") is not None)
    image = os.getenv("COMPEX_AGENT_IMAGE", "purposebound-finance-agent:local")
    image_check = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        check=False,
    )
    all_ok &= check("Research agent image", image_check.returncode == 0, image)
    model_base = os.getenv("MODEL_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    try:
        response = httpx.get(f"{model_base}/models", timeout=5, headers={
            "Authorization": f"Bearer {os.getenv('MODEL_API_KEY', 'local')}"
        })
        all_ok &= check("Model endpoint", response.is_success, f"HTTP {response.status_code}")
    except httpx.HTTPError as exc:
        all_ok &= check("Model endpoint", False, str(exc))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
