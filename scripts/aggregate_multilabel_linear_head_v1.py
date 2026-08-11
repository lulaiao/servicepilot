#!/usr/bin/env python3
"""Validate and aggregate the frozen four-seed multi-label head screen."""

import argparse
import hashlib
import json
import statistics
from pathlib import Path

EXPECTED_SEEDS = (20260901, 20260902, 20260903, 20260904)
METRICS = (
    "macro_f1",
    "exact_set_accuracy",
    "complaint_escalation_false_positive_rate",
)
RESOURCE_METRICS = (
    "embedding_seconds",
    "head_training_seconds",
    "peak_vram_allocated_mib",
    "peak_rss_mib",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": round(statistics.mean(values), 4),
        "population_std": round(statistics.pstdev(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", type=Path, nargs="+", required=True)
    parser.add_argument("--shortcut-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report_pairs = [(path, json.loads(path.read_text(encoding="utf-8"))) for path in args.reports]
    report_pairs.sort(key=lambda pair: pair[1]["seed"])
    reports = [payload for _, payload in report_pairs]
    seeds = tuple(payload["seed"] for payload in reports)
    if seeds != EXPECTED_SEEDS:
        raise ValueError(f"expected seeds {EXPECTED_SEEDS}, got {seeds}")

    invariant_fields = ("protocol_sha256", "dataset_sha256", "model_revision")
    invariants = {field: {payload[field] for payload in reports} for field in invariant_fields}
    inconsistent = {field: values for field, values in invariants.items() if len(values) != 1}
    if inconsistent:
        raise ValueError(f"inconsistent formal-run inputs: {inconsistent}")
    if any(payload["sealed_accessed"] for payload in reports):
        raise ValueError("formal development screen unexpectedly accessed sealed data")
    if any(payload["threshold_tuned_on_dev"] for payload in reports):
        raise ValueError("formal development screen unexpectedly tuned its threshold")

    shortcut = json.loads(args.shortcut_audit.read_text(encoding="utf-8"))
    dataset_sha = next(iter(invariants["dataset_sha256"]))
    if shortcut["dataset_sha256"] != dataset_sha:
        raise ValueError("shortcut audit and formal runs used different datasets")

    payload = {
        "schema_version": "servicepilot-multilabel-linear-head-v1-formal-decision",
        "seeds": list(seeds),
        "run_count": len(reports),
        "protocol_sha256": next(iter(invariants["protocol_sha256"])),
        "dataset_sha256": dataset_sha,
        "model_revision": next(iter(invariants["model_revision"])),
        "all_runs_passed_development_gates": all(item["passed"] for item in reports),
        "metrics": {
            metric: summary([float(item[metric]) for item in reports]) for metric in METRICS
        },
        "per_label_f1": {
            label: summary([float(item["per_label"][label]["f1"]) for item in reports])
            for label in reports[0]["per_label"]
        },
        "resources": {
            metric: summary([float(item["resources"][metric]) for item in reports])
            for metric in RESOURCE_METRICS
        },
        "runs": [
            {
                "seed": item["seed"],
                "report": str(path),
                "report_sha256": sha256(path),
                "head": item["head_output"],
                "head_sha256": item["head_sha256"],
            }
            for path, item in report_pairs
        ],
        "shortcut_audit": {
            "path": str(args.shortcut_audit),
            "sha256": sha256(args.shortcut_audit),
            "lexical_centroid_exact_set_accuracy": shortcut[
                "lexical_centroid_exact_set_accuracy"
            ],
            "complaint_escalation_lexical_f1": shortcut["lexical_centroid_per_label"][
                "complaint_escalation"
            ]["f1"],
        },
        "decision": "accept_as_synthetic_development_candidate_only",
        "integration_allowed": False,
        "next_gate": "independently_authored_frozen_multilabel_holdout",
        "sealed_accessed": False,
        "claim_scope": "four_seed_synthetic_development_screen",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
