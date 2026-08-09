"""V4 pair dataset builder: official CSV -> public records -> counterfactual pairs.

Builds the disjoint calibration (development) and confirmatory (untouched)
case sets, computes stable public-field hashes and per-variant hashes, and
writes ``data/v4/v4_signal_manifest.json`` plus a frozen copy at
``results/v4/manifests/v4-signal-freeze.json``.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from purposebench.utils import (
    canonical_json,
    git_provenance,
    sha256_file,
    sha256_json,
    sha256_text,
)
from purposebench.v2.datasets.common import normalize_public_value
from purposebench.v4.signals import (
    SignalSpec,
    case_seed,
    fraud_public_features,
    generate_pair,
    hardship_public_features,
    reference_classifier_stats,
    signal_spec_from_config,
)

HMDA_APPROVED_FIELDS: tuple[str, ...] = (
    "activity_year",
    "state_code",
    "county_code",
    "census_tract",
    "action_taken",
    "loan_type",
    "loan_purpose",
    "lien_status",
    "occupancy_type",
    "loan_amount",
    "income",
    "debt_to_income_ratio",
    "loan_to_value_ratio",
    "interest_rate",
    "applicant_age",
    "derived_sex",
    "derived_race",
    "derived_ethnicity",
)

CFPB_APPROVED_FIELDS: tuple[str, ...] = (
    "date_received",
    "product",
    "sub_product",
    "issue",
    "sub_issue",
    "company_public_response",
    "company_response_to_consumer",
    "company",
    "state",
    "zip_code",
    "submitted_via",
    "date_sent_to_company",
    "timely_response",
)

CFPB_COLUMN_MAP: dict[str, str] = {
    "Date received": "date_received",
    "Product": "product",
    "Sub-product": "sub_product",
    "Issue": "issue",
    "Sub-issue": "sub_issue",
    "Company public response": "company_public_response",
    "Company": "company",
    "State": "state",
    "ZIP code": "zip_code",
    "Submitted via": "submitted_via",
    "Date sent to company": "date_sent_to_company",
    "Company response to consumer": "company_response_to_consumer",
    "Timely response?": "timely_response",
}


def _csv_rows(path: Path, encoding: str) -> list[dict[str, str]]:
    with path.open("r", encoding=encoding, newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _hash_public(public: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(public).encode("utf-8")).hexdigest()


def _load_hmda(raw_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _csv_rows(raw_path, "utf-8")
    quirks: dict[str, Any] = {
        "rows_total": len(rows),
        "rows_dropped_missing_loan_amount_or_action": 0,
    }
    records: list[dict[str, Any]] = []
    for row in rows:
        public = {
            field: normalize_public_value(row.get(field)) for field in HMDA_APPROVED_FIELDS
        }
        if public["loan_amount"] is None or public["action_taken"] is None:
            quirks["rows_dropped_missing_loan_amount_or_action"] += 1
            continue
        public["source_record_id"] = _hash_public(public)
        records.append({"public_fields": public, "features": fraud_public_features(public)})
    return records, quirks


def _load_cfpb(raw_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _csv_rows(raw_path, "utf-8-sig")
    quirks: dict[str, Any] = {
        "rows_total": len(rows),
        "rows_dropped_missing_complaint_id": 0,
    }
    records: list[dict[str, Any]] = []
    for row in rows:
        public: dict[str, Any] = {}
        for source_name, output_name in CFPB_COLUMN_MAP.items():
            public[output_name] = normalize_public_value(row.get(source_name))
        complaint_id = normalize_public_value(row.get("Complaint ID"))
        if complaint_id is None:
            quirks["rows_dropped_missing_complaint_id"] += 1
            continue
        public["complaint_id"] = complaint_id
        public["source_record_id"] = complaint_id
        records.append({"public_fields": public, "features": hardship_public_features(public)})
    return records, quirks


def load_records(spec: SignalSpec, raw_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if spec.signal_id == "fraud_signal":
        return _load_hmda(raw_path)
    if spec.signal_id == "hardship_signal":
        return _load_cfpb(raw_path)
    raise ValueError(f"no loader for signal {spec.signal_id}")


def features_from_public(spec: SignalSpec, public: dict[str, Any]) -> dict[str, float]:
    if spec.signal_id == "fraud_signal":
        return fraud_public_features(public)
    if spec.signal_id == "hardship_signal":
        return hardship_public_features(public)
    raise ValueError(f"no feature encoder for signal {spec.signal_id}")


def ordered_corpus(
    records: list[dict[str, Any]], master_seed: int
) -> list[dict[str, Any]]:
    """Stable deterministic record ordering shared by calibration/confirmatory."""
    return sorted(
        records,
        key=lambda rec: sha256_text(
            f"{rec['public_fields']['source_record_id']}:{master_seed}"
        ),
    )


def _case_tag(spec: SignalSpec) -> str:
    return spec.signal_id.removesuffix("_signal")


def _emit_pairs(
    spec: SignalSpec,
    selected: list[dict[str, Any]],
    split: str,
    master_seed: int,
    s_bar: float,
    generator_version: str,
    start_index: int,
) -> list[dict[str, Any]]:
    tag = _case_tag(spec)
    pairs: list[dict[str, Any]] = []
    for offset, rec in enumerate(selected):
        index = start_index + offset
        pair = generate_pair(
            spec,
            features=rec["features"],
            public_fields=rec["public_fields"],
            case_id=f"{tag}_{index:05d}",
            pair_id=f"{tag}_pair_{index:05d}",
            split=split,
            case_seed_value=case_seed(master_seed, index),
            s_bar=s_bar,
            generator_version=generator_version,
        )
        pairs.append(pair)
    return pairs


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(canonical_json(record) + "\n")


def write_targets_csv(
    path: Path,
    groups: list[tuple[SignalSpec, list[dict[str, Any]]]],
) -> None:
    """Calibration-only shard of oracle inputs/labels for statistics sanity checks."""
    union_columns: list[str] = []
    for spec, _ in groups:
        for column in ("signal_id", "case_id", "variant", "confidential_value",
                       "a_label", "b_label", "a_pos", "b_pos", "a_prob_low",
                       "a_prob_high", "b_prob"):
            if column not in union_columns:
                union_columns.append(column)
        for column in list(spec.feature_columns) + ["s"]:
            if column not in union_columns:
                union_columns.append(column)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=union_columns)
        writer.writeheader()
        for spec, pairs in groups:
            for pair in pairs:
                feats = features_from_public(spec, pair["public_fields_approved"])
                for variant, confidential_key, label_key, prob_key in (
                    ("A", "confidential", "a_label", "a_low"),
                    ("B", "confidential_alt", "a_label_alt", "a_high"),
                ):
                    row: dict[str, Any] = {
                        "signal_id": pair["signal_id"],
                        "case_id": pair["case_id"],
                        "variant": variant,
                        "confidential_value": pair[confidential_key][spec.signal_field],
                        "a_label": pair[label_key],
                        "b_label": pair["b_label"],
                        "a_pos": int(pair[label_key] == spec.authorized_action_pos),
                        "b_pos": int(pair["b_label"] == spec.prohibited_action_pos),
                        "a_prob_low": pair["oracle_probs"]["a_low"],
                        "a_prob_high": pair["oracle_probs"]["a_high"],
                        "b_prob": pair["oracle_probs"]["b"],
                    }
                    for column in list(spec.feature_columns) + ["s"]:
                        row[column] = feats.get(column)
                    writer.writerow(row)


def correlation_statistics(
    spec: SignalSpec, calib_pairs: list[dict[str, Any]]
) -> dict[str, float]:
    n = len(calib_pairs)
    low_pos = [1.0 if pair["a_label"] == spec.authorized_action_pos else 0.0 for pair in calib_pairs]
    high_pos = [1.0 if pair["a_label_alt"] == spec.authorized_action_pos else 0.0 for pair in calib_pairs]
    b_pos = [1.0 if pair["b_label"] == spec.prohibited_action_pos else 0.0 for pair in calib_pairs]
    indicator = [0.0] * n + [1.0] * n
    authorized = low_pos + high_pos
    prohibited = b_pos + b_pos
    phi_authorized = float(np.corrcoef(indicator, authorized)[0, 1])
    phi_prohibited = float(np.corrcoef(indicator, prohibited)[0, 1])
    return {
        "p_pos_given_low": float(np.mean(low_pos)),
        "p_pos_given_high": float(np.mean(high_pos)),
        "empirical_authorized_shift": float(np.mean(high_pos) - np.mean(low_pos)),
        "p_b_pos": float(np.mean(b_pos)),
        "phi_confidential_authorized": phi_authorized,
        "phi_confidential_prohibited": phi_prohibited,
    }


def build_dataset(*, root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    master_seed = int(cfg["seed"])
    generator_version = str(cfg.get("generator_version", "v4-signal-generator-0.1.0"))
    out = cfg["output"]
    signals_report: dict[str, Any] = {}
    target_groups: list[tuple[SignalSpec, list[dict[str, Any]]]] = []
    all_calib: list[dict[str, Any]] = []
    all_confirm: list[dict[str, Any]] = []
    for signal_id, s_config in cfg["signals"].items():
        spec = signal_spec_from_config(signal_id, s_config)
        raw_path = root / spec.base_dataset_path
        calib_count = int(s_config["counts"]["calib"])
        confirm_count = int(s_config["counts"]["confirm"])

        records, quirks = load_records(spec, raw_path)
        if len(records) < calib_count + confirm_count:
            raise ValueError(
                f"{signal_id}: {len(records)} usable records < required "
                f"{calib_count + confirm_count}"
            )
        s_bar = float(np.mean([rec["features"]["s"] for rec in records]))
        ordered = ordered_corpus(records, master_seed)

        calib_pairs = _emit_pairs(
            spec,
            ordered[:calib_count],
            "CALIBRATION",
            master_seed,
            s_bar,
            generator_version,
            start_index=1,
        )
        confirm_pairs = _emit_pairs(
            spec,
            ordered[calib_count : calib_count + confirm_count],
            "CONFIRMATORY",
            master_seed,
            s_bar,
            generator_version,
            start_index=calib_count + 1,
        )
        all_calib.extend(calib_pairs)
        all_confirm.extend(confirm_pairs)
        target_groups.append((spec, list(calib_pairs)))

        cases = [
            {
                "features": features_from_public(spec, pair["public_fields_approved"]),
                "label_low": int(pair["a_label"] == spec.authorized_action_pos),
                "label_high": int(pair["a_label_alt"] == spec.authorized_action_pos),
            }
            for pair in calib_pairs
        ]
        ref = reference_classifier_stats(spec, cases, seed=master_seed)

        signals_report[signal_id] = {
            "signal_field": spec.signal_field,
            "signal_values": list(spec.signal_values),
            "dataset_id": spec.dataset_id,
            "base_dataset": spec.base_dataset_path,
            "base_dataset_sha256": sha256_file(raw_path),
            "authorized_purpose": spec.authorized_purpose,
            "authorized_actions": [spec.authorized_action_pos, spec.authorized_action_neg],
            "prohibited_purpose": spec.prohibited_purpose,
            "prohibited_actions": [spec.prohibited_action_pos, spec.prohibited_action_neg],
            "oracle_params": {
                "low_prob": spec.oracle_low_prob,
                "high_prob": spec.oracle_high_prob,
                "public_amp": spec.oracle_public_amp,
                "prohibited_shift": spec.prohibited_shift,
                "s_bar": s_bar,
            },
            "generation_seed": master_seed,
            "generator_version": generator_version,
            "signal_distribution": "variant A LOW / variant B HIGH per base case",
            "ground_truth_relationship": (
                "authorized label = public baseline + confidential shift + "
                "seeded Bernoulli noise; prohibited label derived from public "
                "fields only, invariant across the A/B pair"
            ),
            "noise_model": "bernoulli_outcome seeded per case",
            "source_records_scanned": len(records),
            "data_quirk_notes": quirks,
            "counts": {
                "calib_pairs": len(calib_pairs),
                "confirm_pairs": len(confirm_pairs),
            },
            "correlation_statistics": correlation_statistics(spec, calib_pairs),
            "calibration_reference_baccs": ref,
        }

    calib_path = root / out["calib_dir"] / "pairs.jsonl"
    confirm_path = root / out["confirm_dir"] / "pairs.jsonl"
    write_jsonl(calib_path, all_calib)
    write_jsonl(confirm_path, all_confirm)

    targets_path = root / out["targets_csv"]
    write_targets_csv(targets_path, target_groups)

    output_files = {
        "calib_pairs": {
            "path": str(calib_path.relative_to(root)),
            "sha256": sha256_file(calib_path),
        },
        "confirm_pairs": {
            "path": str(confirm_path.relative_to(root)),
            "sha256": sha256_file(confirm_path),
        },
        "targets_csv": {
            "path": str(targets_path.relative_to(root)),
            "sha256": sha256_file(targets_path),
        },
    }
    manifest_payload: dict[str, Any] = {
        "protocol": cfg.get("protocol_id", "protocol-v4-purpose-selectivity"),
        "config_version": int(cfg.get("version", 1)),
        "generator_version": generator_version,
        "generation_seed": master_seed,
        "git": git_provenance(root),
        "signals": signals_report,
        "output_files": output_files,
    }
    manifest_sha = sha256_json(manifest_payload)
    manifest_payload["manifest_sha256"] = manifest_sha

    manifest_path = root / out["manifest"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(canonical_json(manifest_payload) + "\n", encoding="utf-8")
    freeze_path = root / out["freeze"]
    freeze_path.parent.mkdir(parents=True, exist_ok=True)
    freeze_path.write_text(canonical_json(manifest_payload) + "\n", encoding="utf-8")
    return manifest_payload
