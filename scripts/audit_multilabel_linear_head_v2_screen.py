#!/usr/bin/env python3
"""Validate and formalize the frozen v2 representation screen."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = json.loads(args.result.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    dataset = json.loads(args.dataset_manifest.read_text(encoding="utf-8"))
    if result["protocol_sha256"] != sha256(args.protocol):
        raise RuntimeError("screen result protocol hash mismatch")
    if result["dataset_sha256"] != dataset["output_sha256"]:
        raise RuntimeError("screen result dataset hash mismatch")
    if result["threshold_tuned"] or result["sealed_accessed"]:
        raise RuntimeError("v2 screen violated the frozen development-only contract")
    if result["split_counts"]["sealed_test"] != 0:
        raise RuntimeError("v2 screen unexpectedly contains sealed records")

    representations = {
        item["representation"]["id"]: item for item in result["representation_results"]
    }
    declared = {item["id"] for item in protocol["representations"]}
    if set(representations) != declared:
        raise RuntimeError("screened representations differ from the frozen protocol")
    required = protocol["acceptance_gates"]["required_seed_pass_count"]
    eligible = {
        name: item
        for name, item in representations.items()
        if item["passed_seed_count"] == required
    }
    if result["selected_representation"] not in eligible:
        raise RuntimeError("selected representation did not pass every seed gate")
    selected = representations[result["selected_representation"]]
    head_records = []
    for seed_result in selected["seed_results"]:
        path = Path(seed_result["head"])
        if sha256(path) != seed_result["head_sha256"]:
            raise RuntimeError(f"selected head hash mismatch: {path}")
        head_records.append(
            {
                "seed": seed_result["seed"],
                "path": str(path),
                "sha256": seed_result["head_sha256"],
            }
        )

    baseline = representations["raw_attention_masked_mean"]
    instructed = representations["instruction_last_token"]
    latency_increase = instructed["embedding_seconds"] / baseline["embedding_seconds"] - 1
    payload = {
        "schema_version": "servicepilot-multilabel-linear-head-v2-formal-decision",
        "result": str(args.result),
        "result_sha256": sha256(args.result),
        "protocol_sha256": sha256(args.protocol),
        "dataset_manifest_sha256": sha256(args.dataset_manifest),
        "eligible_representations": sorted(eligible),
        "selected_representation": result["selected_representation"],
        "selected_metric_summary": selected["metric_summary"],
        "selected_embedding_seconds": selected["embedding_seconds"],
        "selected_heads": head_records,
        "instruction_last_token_metric_summary": instructed["metric_summary"],
        "instruction_last_token_embedding_seconds": instructed["embedding_seconds"],
        "instruction_latency_increase_fraction": round(latency_increase, 4),
        "decision": "accept_raw_mean_as_v2_development_candidate_only",
        "instruction_last_token_decision": "reject_higher_cost_lower_quality",
        "agent_integration_allowed": False,
        "next_gate": "independently_authored_multilabel_holdout_v2",
        "consumed_holdout_v1_reuse_allowed": False,
        "threshold_tuning_allowed": False,
        "sealed_accessed": False,
        "claim_scope": "balanced_synthetic_dev_representation_selection",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
