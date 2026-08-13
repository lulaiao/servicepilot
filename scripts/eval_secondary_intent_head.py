#!/usr/bin/env python3
"""Compare a fixed multi-label secondary head with saved generative outputs."""

import argparse
import hashlib
import json
from pathlib import Path

from servicepilot.eval.composition_adversarial import build_composition_adversarial_v1
from servicepilot.eval.models import Intent, ScenarioSpec
from servicepilot.routing.secondary_head import CharNgramCentroidBinaryHead
from servicepilot.training.classifier_data import classifier_target
from servicepilot.training.classifier_v5_data import build_classifier_v5_sft
from servicepilot.training.data_models import DataSplit


def utterance(record: object) -> str:
    return record.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1]


def metrics(gold: list[bool], predicted: list[bool]) -> dict[str, float | int]:
    tp = sum(g and p for g, p in zip(gold, predicted, strict=True))
    fp = sum(not g and p for g, p in zip(gold, predicted, strict=True))
    fn = sum(g and not p for g, p in zip(gold, predicted, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "count": len(gold),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "accuracy": round(sum(g == p for g, p in zip(gold, predicted, strict=True)) / len(gold), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-report", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    train_examples = []
    for record in build_classifier_v5_sft():
        if record.split is not DataSplit.TRAIN:
            continue
        target = json.loads(record.messages[1]["content"])
        if target["primary_intent"] != Intent.DELIVERY_DELAY.value:
            continue
        train_examples.append(
            (
                utterance(record),
                Intent.COMPLAINT_ESCALATION.value in target["secondary_intents"],
            )
        )
    head = CharNgramCentroidBinaryHead.fit(tuple(train_examples))
    augmented_examples = list(train_examples)
    for case in build_composition_adversarial_v1():
        if case.model_primary is not Intent.DELIVERY_DELAY:
            continue
        if case.category in {"explicit_pair", "three_intent"}:
            augmented_examples.append((case.text, True))
        elif case.category in {
            "negated_escalation",
            "conditional_future",
            "historical_request",
            "delivery_only",
        }:
            augmented_examples.append((case.text, False))
    augmented_head = CharNgramCentroidBinaryHead.fit(tuple(augmented_examples))
    scenarios = tuple(
        ScenarioSpec.model_validate_json(line)
        for line in args.catalog.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    source = json.loads(args.model_report.read_text(encoding="utf-8"))
    records = source["learned_extractor_agent"]["classifier_records"]
    selected = []
    for scenario, record in zip(scenarios, records, strict=True):
        prediction = record["prediction"]
        if prediction["primary_intent"] != Intent.DELIVERY_DELAY.value:
            continue
        gold_target = classifier_target(scenario)
        gold = Intent.COMPLAINT_ESCALATION in gold_target.secondary_intents
        generated = Intent.COMPLAINT_ESCALATION.value in prediction["secondary_intents"]
        head_prediction = head.predict(scenario.user_utterance)
        augmented_prediction = augmented_head.predict(scenario.user_utterance)
        selected.append(
            {
                "scenario_id": scenario.scenario_id,
                "gold": gold,
                "generative": generated,
                "head": head_prediction.positive,
                "head_margin": round(head_prediction.margin, 6),
                "augmented_head": augmented_prediction.positive,
                "augmented_head_margin": round(augmented_prediction.margin, 6),
            }
        )
    gold = [item["gold"] for item in selected]
    generative = [item["generative"] for item in selected]
    head_values = [item["head"] for item in selected]
    augmented_values = [item["augmented_head"] for item in selected]
    payload = {
        "schema_version": "servicepilot-secondary-intent-head-dev-v1",
        "train_source": "classifier_v5_train_delivery_primary_only",
        "train_count": len(train_examples),
        "train_positive_count": sum(label for _, label in train_examples),
        "train_negative_count": sum(not label for _, label in train_examples),
        "augmented_train_count": len(augmented_examples),
        "augmented_train_positive_count": sum(label for _, label in augmented_examples),
        "augmented_train_negative_count": sum(not label for _, label in augmented_examples),
        "decision_rule": "positive_cosine_similarity_greater_than_negative; fixed_zero_margin",
        "model_report": str(args.model_report),
        "model_report_sha256": hashlib.sha256(args.model_report.read_bytes()).hexdigest(),
        "catalog": str(args.catalog),
        "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        "generative_secondary": metrics(gold, generative),
        "independent_secondary_head": metrics(gold, head_values),
        "adversarial_augmented_secondary_head": metrics(gold, augmented_values),
        "records": selected,
        "claim_scope": "reused_dev_cpu_representation_screen",
        "sealed_accessed": False,
        "threshold_tuned_on_dev": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
