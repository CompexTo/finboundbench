"""Minimal governed-execution acceptance workload.

It proves that approved projection values are available inside the container
without echoing those values into logs or output artifacts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

INPUT = Path("/input/projection.json")
OUTPUT = Path("/output/result.json")


def fail(message: str) -> None:
    raise RuntimeError(message)


raw = INPUT.read_bytes()
projection: dict[str, Any] = json.loads(raw)
selected = projection.get("selectedFields")
denied = projection.get("deniedFields")
records = projection.get("records")
contract_hash = projection.get("contractHash")

if not isinstance(selected, list) or not selected or len(set(selected)) != len(selected):
    fail("selectedFields must be a nonempty unique list")
if not isinstance(denied, list) or set(selected) & set(denied):
    fail("deniedFields is invalid")
if not isinstance(records, list) or not records:
    fail("records must be a nonempty list")
if not isinstance(contract_hash, str) or len(contract_hash) != 64:
    fail("contractHash must be a SHA-256")

expected = set(selected)
for record in records:
    if not isinstance(record, dict) or set(record) != expected:
        fail("record fields differ from the approved projection")
    if set(record) & set(denied):
        fail("a denied field reached the workload")

result = {
    "schemaVersion": "purposebound-finance.governed-gate-result.v2",
    "status": "APPROVED_DATA_AVAILABLE",
    "contractHash": contract_hash,
    "projectionSha256": hashlib.sha256(raw).hexdigest(),
    "selectedFields": sorted(selected),
    "recordCount": len(records),
    "confidentialValuesReleased": False,
}
OUTPUT.write_text(
    json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
    encoding="utf-8",
)
print(
    json.dumps(
        {
            "event": "governed_gate_complete",
            "status": result["status"],
            "projectionSha256": result["projectionSha256"],
            "recordCount": result["recordCount"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
)
