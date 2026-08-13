#!/usr/bin/env python3
"""Measure lexical shortcut strength in the multi-label composition pilot."""

import argparse
import hashlib
import json
from pathlib import Path

from servicepilot.eval.models import Intent
from servicepilot.routing.secondary_head import CharNgramCentroidBinaryHead
from servicepilot.training.multilabel_composition_data import MultiLabelCompositionRecord

LABELS = (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION, Intent.PARTIAL_REFUND)


def shingles(text: str, size: int = 5) -> set[str]:
    value = "".join(text.lower().split())
    return {value[index : index + size] for index in range(max(1, len(value) - size + 1))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = tuple(
        MultiLabelCompositionRecord.model_validate_json(line)
        for line in args.dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    train = tuple(item for item in records if item.split == "train")
    dev = tuple(item for item in records if item.split == "dev")
    predictions: dict[Intent, list[bool]] = {}
    per_label = {}
    for label in LABELS:
        head = CharNgramCentroidBinaryHead.fit(
            tuple((item.text, label in item.labels) for item in train)
        )
        predicted = [head.predict(item.text).positive for item in dev]
        predictions[label] = predicted
        gold = [label in item.labels for item in dev]
        tp = sum(g and p for g, p in zip(gold, predicted, strict=True))
        fp = sum(not g and p for g, p in zip(gold, predicted, strict=True))
        fn = sum(g and not p for g, p in zip(gold, predicted, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label.value] = {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    exact = sum(
        all(predictions[label][index] == (label in item.labels) for label in LABELS)
        for index, item in enumerate(dev)
    ) / len(dev)
    train_shingles = [(item.record_id, shingles(item.text)) for item in train]
    nearest = []
    for item in dev:
        value = shingles(item.text)
        best_id, best_score = max(
            (
                (record_id, len(value & candidate) / len(value | candidate))
                for record_id, candidate in train_shingles
            ),
            key=lambda pair: pair[1],
        )
        nearest.append(
            {"dev_id": item.record_id, "train_id": best_id, "score": round(best_score, 4)}
        )
    payload = {
        "schema_version": "servicepilot-multilabel-shortcut-audit-v1",
        "dataset": str(args.dataset),
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "lexical_centroid_per_label": per_label,
        "lexical_centroid_exact_set_accuracy": round(exact, 4),
        "nearest_train_similarity": {
            "mean": round(sum(item["score"] for item in nearest) / len(nearest), 4),
            "max": max(item["score"] for item in nearest),
            "records": nearest,
        },
        "claim_scope": "dataset_difficulty_audit",
        "sealed_accessed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                **payload,
                "nearest_train_similarity": {
                    key: value
                    for key, value in payload["nearest_train_similarity"].items()
                    if key != "records"
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
