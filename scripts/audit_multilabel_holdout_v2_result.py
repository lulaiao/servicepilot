#!/usr/bin/env python3
"""Validate and formalize the consumed multi-label holdout v2 result."""

import argparse
import hashlib
import json
import statistics
from pathlib import Path


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
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--candidate-decision", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = json.loads(args.result.read_text(encoding="utf-8"))
    freeze = json.loads(args.freeze_manifest.read_text(encoding="utf-8"))
    decision = json.loads(args.candidate_decision.read_text(encoding="utf-8"))
    if result["catalog_sha256"] != freeze["catalog_sha256"]:
        raise RuntimeError("result catalog differs from frozen v2 catalog")
    if result["protocol_sha256"] != freeze["protocol_sha256"]:
        raise RuntimeError("result protocol differs from frozen v2 protocol")
    if result["candidate_decision_sha256"] != sha256(args.candidate_decision):
        raise RuntimeError("result candidate decision hash mismatch")
    expected = {item["seed"]: item["sha256"] for item in decision["selected_heads"]}
    if any(expected[item["seed"]] != item["head_sha256"] for item in result["seed_results"]):
        raise RuntimeError("result contains an undeclared v2 head")
    if result["threshold_tuned"] or result["selection_or_tuning_allowed"]:
        raise RuntimeError("sealed v2 no-tuning contract was violated")
    metrics = {
        metric: summary([float(item[metric]) for item in result["seed_results"]])
        for metric in (
            "macro_f1",
            "exact_set_accuracy",
            "complaint_escalation_false_positive_rate",
        )
    }
    per_label = {
        label: {
            metric: summary(
                [float(item["per_label"][label][metric]) for item in result["seed_results"]]
            )
            for metric in ("precision", "recall", "f1")
        }
        for label in result["seed_results"][0]["per_label"]
    }
    payload = {
        "schema_version": "servicepilot-multilabel-holdout-v2-decision",
        "result": str(args.result),
        "result_sha256": sha256(args.result),
        "freeze_manifest_sha256": sha256(args.freeze_manifest),
        "candidate_decision_sha256": sha256(args.candidate_decision),
        "passed_seed_count": result["passed_seed_count"],
        "required_seed_pass_count": result["required_seed_pass_count"],
        "metrics": metrics,
        "per_label": per_label,
        "category_failure_counts": result["category_failure_counts"],
        "diagnosis": [
            "balanced_synthetic_clauses_reduced_recall_bias_but_created_overprediction",
            "lexical_presence_did_not_generalize_to_contextual_label_boundaries",
            "mean_pooling_linear_head_is_insufficient_for_compositional_scope",
            "negligible_seed_variance_rules_out_optimizer_seed_as_primary_cause",
        ],
        "decision": "reject_multilabel_linear_head_v2",
        "agent_integration_allowed": False,
        "holdout_consumed": True,
        "rerun_allowed": False,
        "retuning_on_holdout_allowed": False,
        "next_step": (
            "stop_linear_head_line_and_test_structured_generative_or_cross_encoder_dev_only"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
