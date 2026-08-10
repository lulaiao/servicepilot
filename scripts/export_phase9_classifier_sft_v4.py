#!/usr/bin/env python3
"""Freeze independently authored train/dev classifier SFT v4 data."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.training.classifier_v4_catalog import (
    build_classifier_v4_sft,
    build_classifier_v4_utterances,
)
from servicepilot.training.data_models import DataSplit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    return parser.parse_args()


def _shingles(text: str, size: int = 5) -> set[str]:
    value = "".join(text.lower().split())
    return {value[index : index + size] for index in range(max(1, len(value) - size + 1))}


def main() -> None:
    args = parse_args()
    utterances = build_classifier_v4_utterances()
    records = build_classifier_v4_sft()
    train = [item for item in utterances if item.split is DataSplit.TRAIN]
    dev = [item for item in utterances if item.split is DataSplit.DEV]
    exact_overlap = len({item.text for item in train} & {item.text for item in dev})
    near_pairs = []
    for left in train:
        left_shingles = _shingles(left.text)
        for right in dev:
            right_shingles = _shingles(right.text)
            score = len(left_shingles & right_shingles) / len(left_shingles | right_shingles)
            if score >= 0.8:
                near_pairs.append(
                    {
                        "train_id": left.utterance_id,
                        "dev_id": right.utterance_id,
                        "score": round(score, 4),
                    }
                )
    counts = Counter(item.split.value for item in records)
    intent_counts = Counter(f"{item.split.value}:{item.intent.value}" for item in utterances)
    slot_counts: Counter[str] = Counter()
    for record in records:
        completion = json.loads(record.messages[1]["content"])
        for name, value in completion["slots"].items():
            if value is not None:
                slot_counts[f"{record.split.value}:{name}"] += 1
    passed = (
        counts == {"train": 72, "dev": 36}
        and exact_overlap == 0
        and not near_pairs
        and len({item.record_id for item in records}) == len(records)
    )
    if not passed:
        raise RuntimeError("classifier SFT v4 failed its freeze gates")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(item.model_dump_json() + "\n" for item in records), encoding="utf-8"
    )
    output_sha256 = hashlib.sha256(args.output.read_bytes()).hexdigest()
    payload = {
        "schema_version": "servicepilot-classifier-sft-v4-independent",
        "code_revision": args.code_revision,
        "output": str(args.output),
        "output_sha256": output_sha256,
        "record_count": len(records),
        "split_counts": dict(sorted(counts.items())),
        "intent_split_counts": dict(sorted(intent_counts.items())),
        "visible_slot_counts": dict(sorted(slot_counts.items())),
        "exact_cross_split_overlap_count": exact_overlap,
        "near_duplicate_threshold": 0.8,
        "near_duplicate_count": len(near_pairs),
        "near_duplicates": near_pairs,
        "sealed_record_count": 0,
        "legacy_variant_source_used": False,
        "hard_eval_v2_accessed": False,
        "passed": passed,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
