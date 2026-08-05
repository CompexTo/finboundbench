"""Recompute R0/R1/R2 tables from raw v3 evidence."""
import json
from pathlib import Path
from collections import defaultdict

results_root = Path("results/v3")

# === R1 Position Diagnostic ===
print("=" * 60)
print("R1 POSITION DIAGNOSTIC (from raw events)")
print("=" * 60)

r1_path = results_root / "position-diagnostic/raw/events.jsonl"
r1_events = [json.loads(line) for line in r1_path.read_text(encoding="utf-8").splitlines() if line.strip()]

# By model
r1_by_model = defaultdict(lambda: defaultdict(int))
for e in r1_events:
    model = e.get("expectedModelId", "?")
    status = e.get("status", "?")
    r1_by_model[model][status] += 1

print("\nBy model:")
for model in sorted(r1_by_model.keys()):
    counts = r1_by_model[model]
    total = sum(counts.values())
    passed = counts.get("PASSED", 0)
    denied = counts.get("RELEASE_DENIED", 0)
    failed = counts.get("FAILED", 0)
    print(f"  {model}: {passed}/{total} PASSED, {denied} RELEASE_DENIED, {failed} FAILED")

# By layout
r1_by_layout = defaultdict(lambda: defaultdict(int))
for e in r1_events:
    layout = e.get("layout", "?")
    status = e.get("status", "?")
    r1_by_layout[layout][status] += 1

print("\nBy layout:")
for layout in sorted(r1_by_layout.keys()):
    counts = r1_by_layout[layout]
    total = sum(counts.values())
    passed = counts.get("PASSED", 0)
    denied = counts.get("RELEASE_DENIED", 0)
    print(f"  {layout}: {passed}/{total} PASSED, {denied} RELEASE_DENIED")

r1_total = len(r1_events)
r1_passed = sum(1 for e in r1_events if e["status"] == "PASSED")
r1_denied = sum(1 for e in r1_events if e["status"] == "RELEASE_DENIED")
print(f"\nR1 TOTAL: {r1_passed}/{r1_total} PASSED, {r1_denied} RELEASE_DENIED")

# === R2 Confirmatory Matrix ===
print("\n" + "=" * 60)
print("R2 CONFIRMATORY MATRIX (from raw events)")
print("=" * 60)

r2_path = results_root / "confirmatory-matrix/raw/events.jsonl"
r2_events = [json.loads(line) for line in r2_path.read_text(encoding="utf-8").splitlines() if line.strip()]

# By model
r2_by_model = defaultdict(lambda: defaultdict(int))
for e in r2_events:
    model = e.get("expectedModelId", "?")
    status = e.get("status", "?")
    r2_by_model[model][status] += 1

print("\nBy model:")
for model in sorted(r2_by_model.keys()):
    counts = r2_by_model[model]
    total = sum(counts.values())
    passed = counts.get("PASSED", 0)
    denied = counts.get("RELEASE_DENIED", 0)
    failed = counts.get("FAILED", 0)
    print(f"  {model}: {passed}/{total} PASSED, {denied} RELEASE_DENIED, {failed} FAILED")

# By model x dataset
print("\nBy model x dataset:")
r2_by_model_ds = defaultdict(lambda: defaultdict(int))
for e in r2_events:
    key = (e.get("expectedModelId", "?"), e.get("datasetId", "?"))
    status = e.get("status", "?")
    r2_by_model_ds[key][status] += 1

for (model, ds) in sorted(r2_by_model_ds.keys()):
    counts = r2_by_model_ds[(model, ds)]
    total = sum(counts.values())
    passed = counts.get("PASSED", 0)
    denied = counts.get("RELEASE_DENIED", 0)
    print(f"  {model} x {ds}: {passed}/{total} PASSED, {denied} RELEASE_DENIED")

# By model x condition
print("\nBy model x condition:")
r2_by_model_cond = defaultdict(lambda: defaultdict(int))
for e in r2_events:
    key = (e.get("expectedModelId", "?"), e.get("conditionId", "?"))
    status = e.get("status", "?")
    r2_by_model_cond[key][status] += 1

for (model, cond) in sorted(r2_by_model_cond.keys()):
    counts = r2_by_model_cond[(model, cond)]
    total = sum(counts.values())
    passed = counts.get("PASSED", 0)
    denied = counts.get("RELEASE_DENIED", 0)
    print(f"  {model} x {cond}: {passed}/{total} PASSED, {denied} RELEASE_DENIED")

# Full cross-tabulation: model x dataset x condition
print("\nFull cross-tabulation (model x dataset x condition):")
r2_full = defaultdict(lambda: defaultdict(int))
for e in r2_events:
    key = (e.get("expectedModelId", "?"), e.get("datasetId", "?"), e.get("conditionId", "?"))
    status = e.get("status", "?")
    r2_full[key][status] += 1

for (model, ds, cond) in sorted(r2_full.keys()):
    counts = r2_full[(model, ds, cond)]
    total = sum(counts.values())
    passed = counts.get("PASSED", 0)
    denied = counts.get("RELEASE_DENIED", 0)
    print(f"  {model} x {ds} x {cond}: {passed}/{total} PASSED, {denied} RELEASE_DENIED")

# Verify consistency
r2_total = len(r2_events)
r2_passed = sum(1 for e in r2_events if e["status"] == "PASSED")
r2_denied = sum(1 for e in r2_events if e["status"] == "RELEASE_DENIED")

# Check sum of model cells
model_pass_sum = sum(r2_by_model[m].get("PASSED", 0) for m in r2_by_model)
model_deny_sum = sum(r2_by_model[m].get("RELEASE_DENIED", 0) for m in r2_by_model)

# Check sum of condition cells
cond_pass_sum = sum(v.get("PASSED", 0) for v in r2_full.values())
cond_deny_sum = sum(v.get("RELEASE_DENIED", 0) for v in r2_full.values())

print(f"\nR2 TOTAL: {r2_passed}/{r2_total} PASSED, {r2_denied} RELEASE_DENIED")
print(f"\nConsistency checks:")
print(f"  model_pass_sum={model_pass_sum} == r2_passed={r2_passed}: {model_pass_sum == r2_passed}")
print(f"  model_deny_sum={model_deny_sum} == r2_denied={r2_denied}: {model_deny_sum == r2_denied}")
print(f"  cond_pass_sum={cond_pass_sum} == r2_passed={r2_passed}: {cond_pass_sum == r2_passed}")
print(f"  cond_deny_sum={cond_deny_sum} == r2_denied={r2_denied}: {cond_deny_sum == r2_denied}")

# === Budget ===
print("\n" + "=" * 60)
print("BUDGET (from raw ledgers)")
print("=" * 60)

for ledger_name in ["openrouter-v3-ledger.jsonl", "openrouter-v3-r2-ledger.jsonl"]:
    ledger_path = results_root / "raw/budget" / ledger_name
    if not ledger_path.exists():
        print(f"\n{ledger_name}: MISSING")
        continue
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    reservations = [r for r in rows if r.get("recordType") == "budget_reservation"]
    settlements = [r for r in rows if r.get("recordType") == "budget_settlement"]
    committed = max((r.get("committedAfterReservationEur", 0) for r in reservations), default=0)
    settled = sum(r.get("budgetDebitEur", 0) for r in settlements)
    print(f"\n{ledger_name}:")
    print(f"  Reservations: {len(reservations)}")
    print(f"  Settlements: {len(settlements)}")
    print(f"  Max committed: {committed:.2f} EUR")
    print(f"  Total settled: {settled:.2f} EUR")
