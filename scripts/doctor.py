from __future__ import annotations

import os
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
    base = os.getenv("COMPEX_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    health = os.getenv("COMPEX_HEALTH_PATH", "/health")
    if os.getenv("COMPEX_MODE", "http") == "http":
        try:
            response = httpx.get(f"{base}{health}", timeout=5)
            all_ok &= check("Compex health", response.is_success, f"HTTP {response.status_code}")
        except Exception as exc:
            all_ok &= check("Compex health", False, str(exc))
    else:
        all_ok &= check("Compex CLI configured", bool(os.getenv("COMPEX_CLI_COMMAND")))
    model_base = os.getenv("MODEL_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/")
    try:
        response = httpx.get(f"{model_base}/models", timeout=5, headers={
            "Authorization": f"Bearer {os.getenv('MODEL_API_KEY', 'local')}"
        })
        all_ok &= check("Model endpoint", response.is_success, f"HTTP {response.status_code}")
    except Exception as exc:
        all_ok &= check("Model endpoint", False, str(exc))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
