"""Run one phase of the governed OpenRouter frontier model matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from run_remote_openrouter_pilot import _image_digest

from purposebench.utils import read_jsonl, sha256_json
from purposebench.v2.frontier_matrix import (
    BUDGET_LEDGER,
    committed_budget_eur,
    load_frontier_matrix,
    reserve_budget,
    settle_budget,
)
from purposebench.v2.pilots import write_new_v2_artifact
from purposebench.v2.remote_pilot import build_remote_manifest, run_remote_pilot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform-root", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/v2/openrouter-frontier-matrix.json"),
    )
    parser.add_argument("--phase", choices=("smoke", "pilot"), required=True)
    parser.add_argument("--model-id", action="append", dest="model_ids")
    parser.add_argument("--image", default="purposebound-finance-v2-gate:local")
    args = parser.parse_args()
    benchmark_root = Path(__file__).resolve().parents[1]
    config, models = load_frontier_matrix(benchmark_root, args.config.resolve())
    requested = set(args.model_ids or config["modelIds"])
    unknown = requested - set(config["modelIds"])
    if unknown:
        raise ValueError(f"unknown frontier model IDs: {sorted(unknown)}")
    phase = config["phases"][args.phase]
    dataset = (benchmark_root / config["dataset"]).resolve()
    local_fallback = (benchmark_root / config["localFallback"]).resolve()
    ledger_path = benchmark_root / BUDGET_LEDGER
    image_digest = _image_digest(args.image)
    successes: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for model in models:
        if model["modelId"] not in requested:
            continue
        slug = model["artifactSlug"]
        artifact_stem = f"openrouter-frontier-{args.phase}-{slug}"
        raw_path = benchmark_root / "results/v2/raw/inference" / f"{artifact_stem}.jsonl"
        manifest_path = benchmark_root / "results/v2/manifests" / f"{artifact_stem}.json"
        if args.phase == "pilot":
            smoke_manifest_path = (
                benchmark_root
                / "results/v2/manifests"
                / f"openrouter-frontier-smoke-{slug}.json"
            )
            if not smoke_manifest_path.exists():
                failures.append(
                    {
                        "modelId": model["modelId"],
                        "errorType": "MissingSmokeGate",
                        "error": "one-record frontier smoke is not complete",
                        "committedMatrixBudgetEur": str(
                            committed_budget_eur(read_jsonl(ledger_path))
                        ),
                    }
                )
                continue
            smoke_manifest = json.loads(smoke_manifest_path.read_text(encoding="utf-8"))
            if (
                smoke_manifest.get("status") != "passed"
                or smoke_manifest.get("model") != model["modelId"]
            ):
                failures.append(
                    {
                        "modelId": model["modelId"],
                        "errorType": "FailedSmokeGate",
                        "error": "one-record frontier smoke did not pass for this model",
                        "committedMatrixBudgetEur": str(
                            committed_budget_eur(read_jsonl(ledger_path))
                        ),
                    }
                )
                continue
        if raw_path.exists() and manifest_path.exists():
            successes.append({"modelId": model["modelId"], "status": "already_complete"})
            continue
        if manifest_path.exists() and not raw_path.exists():
            raise RuntimeError(f"manifest exists without raw artifact for {model['modelId']}")
        if raw_path.exists():
            ledger_rows = read_jsonl(ledger_path)
            settlements = [
                row
                for row in ledger_rows
                if row["recordType"] == "budget_settlement"
                and row["modelId"] == model["modelId"]
                and row["phase"] == args.phase
                and row["outcome"] == "passed"
            ]
            if not settlements:
                raise RuntimeError(f"raw artifact has no passed budget settlement for {model['modelId']}")
            settlement = settlements[-1]
            reservation = next(
                row
                for row in ledger_rows
                if row["recordType"] == "budget_reservation"
                and row["reservationId"] == settlement["reservationId"]
            )
            manifest = build_remote_manifest(benchmark_root, raw_path, local_fallback)
            manifest["frontierMatrix"] = {
                "matrixHash": config["modelMatrixHash"],
                "modelManifest": config["modelManifestPath"],
                "phase": args.phase,
            }
            manifest["budget"] = {
                "reservationId": settlement["reservationId"],
                "authorizedCostEur": reservation["authorizedCostEur"],
                "budgetDebitEur": settlement["budgetDebitEur"],
                "committedMatrixBudgetEur": committed_budget_eur(ledger_rows),
                "totalAuthorizedCostEur": config["totalAuthorizedCostEur"],
                "ledgerArtifact": str(BUDGET_LEDGER).replace("\\", "/"),
                "ledgerPrefixRecordCount": len(ledger_rows),
                "ledgerPrefixHash": sha256_json(ledger_rows),
            }
            destination = write_new_v2_artifact(
                benchmark_root,
                manifest_path.relative_to(benchmark_root),
                manifest,
            )
            successes.append(
                {
                    "modelId": model["modelId"],
                    "status": "manifest_recovered",
                    "raw": str(raw_path),
                    "manifest": str(destination),
                }
            )
            continue
        reservation_id, _ = reserve_budget(
            ledger_path,
            model_id=model["modelId"],
            phase=args.phase,
            authorized_cost_eur=float(config["perInvocationAuthorizedCostEur"]),
            total_authorized_cost_eur=float(config["totalAuthorizedCostEur"]),
        )
        settled = False
        try:
            raw_path = run_remote_pilot(
                benchmark_root=benchmark_root,
                platform_root=args.platform_root.resolve(),
                dataset_path=dataset,
                pair_limit=int(phase["pairLimit"]),
                record_limit=phase["recordLimit"],
                model_manifest=model,
                maximum_authorized_cost_eur=float(
                    config["perInvocationAuthorizedCostEur"]
                ),
                output_name=f"{artifact_stem}.jsonl",
                workload_image_digest=image_digest,
            )
            successful = [
                row for row in read_jsonl(raw_path) if row.get("status") == "passed"
            ][-1]
            debit = float(successful["budgetDebitEur"])
            provider_reported_cost = successful["modelEvidence"].get(
                "providerReportedCost"
            )
            committed = settle_budget(
                ledger_path,
                reservation_id=reservation_id,
                model_id=model["modelId"],
                phase=args.phase,
                budget_debit_eur=debit,
                outcome="passed",
                provider_reported_cost=provider_reported_cost,
            )
            settled = True
            ledger_rows = read_jsonl(ledger_path)
            manifest = build_remote_manifest(
                benchmark_root,
                raw_path,
                local_fallback,
            )
            manifest["frontierMatrix"] = {
                "matrixHash": config["modelMatrixHash"],
                "modelManifest": config["modelManifestPath"],
                "phase": args.phase,
            }
            manifest["budget"] = {
                "reservationId": reservation_id,
                "authorizedCostEur": config["perInvocationAuthorizedCostEur"],
                "budgetDebitEur": debit,
                "providerReportedCost": provider_reported_cost,
                "committedMatrixBudgetEur": committed,
                "totalAuthorizedCostEur": config["totalAuthorizedCostEur"],
                "ledgerArtifact": str(BUDGET_LEDGER).replace("\\", "/"),
                "ledgerPrefixRecordCount": len(ledger_rows),
                "ledgerPrefixHash": sha256_json(ledger_rows),
            }
            destination = write_new_v2_artifact(
                benchmark_root,
                manifest_path.relative_to(benchmark_root),
                manifest,
            )
            successes.append(
                {
                    "modelId": model["modelId"],
                    "status": "passed",
                    "raw": str(raw_path),
                    "manifest": str(destination),
                    "budgetDebitEur": debit,
                }
            )
        except Exception as error:  # noqa: BLE001 - preserve matrix progress
            if not settled:
                committed = settle_budget(
                    ledger_path,
                    reservation_id=reservation_id,
                    model_id=model["modelId"],
                    phase=args.phase,
                    budget_debit_eur=float(config["perInvocationAuthorizedCostEur"]),
                    outcome="failed_conservative_debit",
                )
            failures.append(
                {
                    "modelId": model["modelId"],
                    "errorType": type(error).__name__,
                    "error": str(error),
                    "committedMatrixBudgetEur": str(committed),
                }
            )
    print(json.dumps({"successes": successes, "failures": failures}, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
