#!/usr/bin/env python3
"""Validate and summarize the consumed multi-label holdout result."""

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
    parser.add_argument("--formal-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = json.loads(args.result.read_text(encoding="utf-8"))
    freeze = json.loads(args.freeze_manifest.read_text(encoding="utf-8"))
    formal = json.loads(args.formal_manifest.read_text(encoding="utf-8"))
    seeds = [item["seed"] for item in result["seed_results"]]
    if seeds != formal["seeds"]:
        raise RuntimeError("sealed result seed set differs from the accepted development runs")
    if result["catalog_sha256"] != freeze["catalog_sha256"]:
        raise RuntimeError("sealed result catalog hash differs from the freeze manifest")
    if result["protocol_sha256"] != freeze["protocol_sha256"]:
        raise RuntimeError("sealed result protocol hash differs from the freeze manifest")
    expected_heads = {item["seed"]: item["head_sha256"] for item in formal["runs"]}
    if any(item["head_sha256"] != expected_heads[item["seed"]] for item in result["seed_results"]):
        raise RuntimeError("sealed result contains an undeclared head")
    if result["threshold_tuned"] or result["selection_or_tuning_allowed"]:
        raise RuntimeError("sealed result violated the no-tuning contract")

    metrics = {
        name: summary([float(item[name]) for item in result["seed_results"]])
        for name in (
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
    training_label_prevalence = {
        label: round(count / 240, 4)
        for label, count in {
            "delivery_delay": 210,
            "complaint_escalation": 105,
            "partial_refund": 30,
        }.items()
    }
    payload = {
        "schema_version": "servicepilot-multilabel-holdout-v1-decision",
        "result": str(args.result),
        "result_sha256": sha256(args.result),
        "freeze_manifest_sha256": sha256(args.freeze_manifest),
        "formal_manifest_sha256": sha256(args.formal_manifest),
        "seeds": seeds,
        "passed_seed_count": result["passed_seed_count"],
        "required_seed_pass_count": result["required_seed_pass_count"],
        "metrics": metrics,
        "per_label": per_label,
        "category_failure_counts": result["category_failure_counts"],
        "training_label_prevalence": training_label_prevalence,
        "diagnosis": [
            "delivery_label_prevalence_and_template_shortcut",
            "complaint_paraphrase_generalization_failure",
            "partial_refund_recall_and_label_composition_failure",
            "negligible_seed_variance_points_to_data_representation_not_optimizer_instability",
        ],
        "decision": "reject_multilabel_linear_head_v1",
        "agent_integration_allowed": False,
        "holdout_consumed": True,
        "rerun_allowed": False,
        "retuning_on_holdout_allowed": False,
        "next_step": "redesign_train_only_data_and_representation_then_freeze_new_holdout_version",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
