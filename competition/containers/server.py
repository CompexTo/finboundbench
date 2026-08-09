"""Minimal HTTP /decide endpoint for containerized FinBoundBench submissions.

Standard library only. Submissions that call external LLM APIs read their
credentials from the environment (never commit them) and must keep responses
within the per-decision budget and timeout declared in rules.md.

Run: python server.py  (serves POST /decide on 0.0.0.0:8000)
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


def load_decide() -> Any:
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("submission", "/app/submission/decide.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load /app/submission/decide.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["submission"] = module
    spec.loader.exec_module(module)
    return module.decide


DECIDE = load_decide()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/decide":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        payload: dict[str, Any] = json.loads(self.rfile.read(length).decode("utf-8"))
        try:
            response = DECIDE(payload)
        except Exception as exc:  # noqa: BLE001
            response = {"action": None, "error": str(exc), "cost_usd": 0.0}
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
