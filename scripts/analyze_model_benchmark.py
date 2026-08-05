#!/usr/bin/env python3
"""Derive comparable metrics from a raw local-model benchmark report."""

import argparse
import json
import math
from pathlib import Path
from typing import Any

from servicepilot.eval.routing_dataset import DatasetSplit, build_routing_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    split = DatasetSplit(raw["split"])
    gold = {
        item.example_id: item
        for item in build_routing_dataset()
        if item.split is split
    }
    records: list[dict[str, Any]] = raw["records"]
    labels = [gold[item["example_id"]].primary_intent.value for item in records]
    predictions = [
        item["prediction"]["primary_intent"]
        if item["prediction"] is not None
        else "__invalid__"
        for item in records
    ]
    f1_scores: list[float] = []
    for label in set(labels) | set(predictions):
        true_positive = sum(
            expected == label and predicted == label
            for expected, predicted in zip(labels, predictions, strict=True)
        )
        false_positive = sum(
            expected != label and predicted == label
            for expected, predicted in zip(labels, predictions, strict=True)
        )
        false_negative = sum(
            expected == label and predicted != label
            for expected, predicted in zip(labels, predictions, strict=True)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        f1_scores.append(
            2 * true_positive / denominator if denominator else 0
        )
    latencies = sorted(float(item["latency_seconds"]) for item in records)
    count = len(records)
    metrics = {
        "source": str(args.input),
        "candidate": raw["candidate"],
        "split": split.value,
        "example_count": count,
        "schema_valid_rate": raw["schema_valid_rate"],
        "primary_accuracy": raw["primary_accuracy"],
        "macro_f1": round(sum(f1_scores) / len(f1_scores), 4),
        "secondary_exact_match": round(
            sum(
                item["prediction"] is not None
                and set(item["prediction"]["secondary_intents"])
                == {
                    intent.value
                    for intent in gold[item["example_id"]].secondary_intents
                }
                for item in records
            )
            / count,
            4,
        ),
        "slot_exact_match": round(
            sum(
                item["prediction"] is not None
                and all(
                    item["prediction"]["slots"].get(key) == value
                    for key, value in gold[item["example_id"]].slots.items()
                )
                for item in records
            )
            / count,
            4,
        ),
        "mean_latency_seconds": raw["mean_latency_seconds"],
        "p95_latency_seconds": latencies[math.ceil(0.95 * count) - 1],
        "throughput_examples_per_second": round(
            count / sum(latencies), 4
        ),
        "peak_rss_mib": raw["peak_rss_mib"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
