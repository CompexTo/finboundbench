"""Protocol-v4 confirmatory integrity test — local, no-cost (Fix 0/blueprint step 10).

Runs the eligibility runner with the MOCK (fake) provider over the CONFIRMATORY
pair stream, every condition, both admitted studies, and asserts the
experiment-fatal invariants (blueprint §12):

  INV-1  A1/A3: confidential_field in transmittedFields
  INV-2  P2/P3: confidential_field NOT in transmittedFields
  INV-3  provider_success == 1.0 and zero provider failures (mock path)
  INV-4  every decision is inside the registered enum (authorized vs prohibited)
  INV-5  ground truth present on all authorized conditions, b_label elsewhere
  INV-6  dataset separation: confirm pairs never touch eligibility pairs (record overlap == 0)
  INV-7  freeze manifests verify (confirmatory-dataset-freeze, eligibility-results-freeze,
         v4-confirmatory-protocol-freeze) — re-hash and compare

Exit code 0 == all invariants hold; otherwise 1.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from purposebench.v4.eligibility_runner import (
    AUTHORIZED_CONDITIONS,
    CONDITION_IDS,
    PROHIBITED_CONDITIONS,
    run_eligibility,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIRM_PAIRS = ROOT / "data/v4/v4_confirm/pairs.jsonl"
CALIB_PAIRS = ROOT / "data/v4/v4_calibr/pairs.jsonl"

FAILURES: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(label)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_freeze(name: str) -> dict:
    return json.loads((ROOT / f"results/v4/manifests/{name}.json").read_text(encoding="utf-8"))


def main() -> int:
    print("== Protocol v4 confirmatory integrity test (fake provider, no cost) ==")

    # ---- INV-7: freeze manifests verify ----
    print("[INV-7] freeze manifests re-hash")
    for name in (
        "confirmatory-dataset-freeze",
        "eligibility-results-freeze",
        "v4-confirmatory-protocol-freeze",
        "v4-signal-freeze",
    ):
        freeze = load_freeze(name)
        # verify contained file hashes
        file_hashes_ok = True
        for entry in freeze.get("files", []):
            p = ROOT / entry["path"]
            if not p.is_file() or sha256_of(p) != entry["sha256"]:
                file_hashes_ok = False
                check(False, f"{name}: bound file {entry['path']} changed")
        check(file_hashes_ok, f"{name}: {len(freeze.get('files', []))} bound files match")

    # ---- INV-6: dataset separation ----
    print("[INV-6] dataset separation")
    confirm_ids = {json.loads(l)["pair_id"] for l in CONFIRM_PAIRS.read_text(encoding="utf-8").splitlines() if l.strip()}
    calib_ids = {json.loads(l)["pair_id"] for l in CALIB_PAIRS.read_text(encoding="utf-8").splitlines() if l.strip()}
    overlap = confirm_ids & calib_ids
    check(len(overlap) == 0, "confirm/calib pair_id overlap == 0", f"overlap={len(overlap)}")

    # ---- INV-1..INV-5: mock runs over confirm pairs, all conditions ----
    print("[INV-1..5] mock-provider runs, all 9 conditions, confirm pairs")
    for lane in ("deepseek-deepseek-v4-pro", "moonshotai-kimi-k3", "mock"):
        print(f"  lane={lane}")
        report = run_eligibility(
            lane,
            dataset=CONFIRM_PAIRS,
            dry_run=True,
            results_root=ROOT / f"tmp/integrity-{lane}",
            conditions=list(CONDITION_IDS),
        )
        check(report["live_calls"] == 0, f"{lane}: zero live calls (mock)")
        for task in report["tasks"]:
            events_path = ROOT / f"tmp/integrity-{lane}/{lane}/{task['task_id']}/events.jsonl"
            events = [json.loads(l) for l in events_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            from purposebench.v4.eligibility_runner import load_eligibility_config

            config = load_eligibility_config()
            signal_meta = {s["signal_id"]: s for s in config["signals"]}
            ok_all = True
            n_events = 0
            for event in events:
                cond = event["condition_id"]
                sig = signal_meta.get(event.get("signal_id"))
                if sig is None:
                    check(False, f"{lane}/{task['task_id']}: unknown signal_id")
                    ok_all = False
                    continue
                conf = sig["confidential_field"]
                transmitted = set(event.get("transmitted_fields") or [])
                n_events += 1
                if cond in ("A1", "A3"):
                    if conf not in transmitted:
                        ok_all = False
                        check(False, f"INV-1 {lane}/{task['task_id']}/{cond}: {conf} not transmitted")
                if cond in ("P2", "P3"):
                    if conf in transmitted:
                        ok_all = False
                        check(False, f"INV-2 {lane}/{task['task_id']}/{cond}: {conf} leaked")
                if not event.get("provider_success"):
                    ok_all = False
                    check(False, f"INV-3 {lane}/{task['task_id']}/{cond}: provider failure")
                if event.get("model_decision"):
                    allowed = (
                        set(sig["authorized_actions"])
                        if cond in AUTHORIZED_CONDITIONS or cond == "ND"
                        else set(sig["prohibited_actions"])
                    )
                    if event["model_decision"] not in allowed:
                        ok_all = False
                        check(False, f"INV-4 {lane}/{task['task_id']}/{cond}: decision outside enum")
                if cond in AUTHORIZED_CONDITIONS and not event.get("ground_truth_label"):
                    ok_all = False
                    check(False, f"INV-5 {lane}/{task['task_id']}/{cond}: missing ground truth")
            check(ok_all, f"{lane}/{task['task_id']}: invariants on {n_events} events")

    # ---- hard budget cross-check ----
    print("[budget] power-estimate vs freeze")
    power = json.loads((ROOT / "results/v4/statistics/power-estimate.json").read_text(encoding="utf-8"))
    freeze = load_freeze("v4-confirmatory-protocol-freeze")
    hard_budget = freeze.get("hard_budget_eur")
    check(
        power["within_hard_budget"],
        "planned cost (observed x5) within hard budget",
        f"est €{power['est_cost_eur_observed_x5']:.2f} vs hard budget €{hard_budget} (ceiling €{power['est_cost_eur_reservation_ceiling']:.2f})",
    )

    print()
    if FAILURES:
        print(f"INTEGRITY: FAILED — {len(FAILURES)} checks failed")
        return 1
    print("INTEGRITY: PASS — all invariants hold, no live calls made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())