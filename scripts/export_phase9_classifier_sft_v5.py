#!/usr/bin/env python3
"""Freeze v5 train-only hard negatives while preserving v4 dev."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.training.classifier_v4_catalog import build_classifier_v4_sft
from servicepilot.training.classifier_v5_data import build_classifier_v5_sft
from servicepilot.training.data_models import DataSplit, SFTTrainingRecord


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    return parser.parse_args()


def _text(record: SFTTrainingRecord) -> str:
    prompt = record.messages[0]["content"]
    return prompt.rsplit("用户输入：", maxsplit=1)[-1]


def _shingles(text: str, size: int = 5) -> set[str]:
    value = "".join(text.lower().split())
    return {value[index : index + size] for index in range(max(1, len(value) - size + 1))}


def main() -> None:
    args = parse_args()
    records = build_classifier_v5_sft()
    train = [item for item in records if item.split is DataSplit.TRAIN]
    dev = [item for item in records if item.split is DataSplit.DEV]
    exact_overlap = len({_text(item) for item in train} & {_text(item) for item in dev})
    near_pairs = []
    for left in train:
        left_shingles = _shingles(_text(left))
        for right in dev:
            right_shingles = _shingles(_text(right))
            score = len(left_shingles & right_shingles) / len(left_shingles | right_shingles)
            if score >= 0.8:
                near_pairs.append(
                    {
                        "train_id": left.record_id,
                        "dev_id": right.record_id,
                        "score": round(score, 4),
                    }
                )
    counts = Counter(item.split.value for item in records)
    new_records = [item for item in train if item.source_record_id.startswith("v5-train-")]
    category_counts = Counter(
        item.source_record_id.removeprefix("v5-train-").rsplit("-", maxsplit=1)[0]
        for item in new_records
    )
    dev_bytes = "".join(item.model_dump_json() + "\n" for item in dev).encode()
    v4_dev_bytes = "".join(
        item.model_dump_json() + "\n"
        for item in build_classifier_v4_sft()
        if item.split is DataSplit.DEV
    ).encode()
    dev_changed_from_v4 = dev_bytes != v4_dev_bytes
    passed = (
        counts == {"train": 120, "dev": 36}
        and len(new_records) == 48
        and exact_overlap == 0
        and not near_pairs
        and not dev_changed_from_v4
        and len({item.record_id for item in records}) == len(records)
    )
    if not passed:
        raise RuntimeError("classifier SFT v5 failed its freeze gates")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(item.model_dump_json() + "\n" for item in records).encode()
    args.output.write_bytes(encoded)
    payload = {
        "schema_version": "servicepilot-classifier-sft-v5-hard-negative",
        "code_revision": args.code_revision,
        "output": str(args.output),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "record_count": len(records),
        "split_counts": dict(sorted(counts.items())),
        "new_train_record_count": len(new_records),
        "new_train_category_counts": dict(sorted(category_counts.items())),
        "dev_record_sha256": hashlib.sha256(dev_bytes).hexdigest(),
        "dev_changed_from_v4": dev_changed_from_v4,
        "exact_cross_split_overlap_count": exact_overlap,
        "near_duplicate_threshold": 0.8,
        "near_duplicate_count": len(near_pairs),
        "sealed_record_count": 0,
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
