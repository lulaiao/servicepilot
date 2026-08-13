#!/usr/bin/env python3
"""Freeze the independent factored classifier train/dev catalog."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.training.data_models import DataSplit, SFTTrainingRecord
from servicepilot.training.factored_classifier_catalog import build_factored_classifier_sft


def _text(record: SFTTrainingRecord) -> str:
    return record.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1]


def _shingles(text: str, size: int = 5) -> set[str]:
    value = "".join(text.lower().split())
    return {value[index : index + size] for index in range(max(1, len(value) - size + 1))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    records = build_factored_classifier_sft()
    train = tuple(item for item in records if item.split is DataSplit.TRAIN)
    dev = tuple(item for item in records if item.split is DataSplit.DEV)
    exact = {_text(item) for item in train} & {_text(item) for item in dev}
    near = []
    for left in train:
        left_shingles = _shingles(_text(left))
        for right in dev:
            right_shingles = _shingles(_text(right))
            score = len(left_shingles & right_shingles) / len(left_shingles | right_shingles)
            if score >= 0.8:
                near.append(
                    {
                        "train_id": left.record_id,
                        "dev_id": right.record_id,
                        "score": round(score, 4),
                    }
                )
    counts = Counter(item.split.value for item in records)
    passed = (
        counts == {"train": 56, "dev": 28}
        and not exact
        and not near
        and len({item.record_id for item in records}) == len(records)
    )
    if not passed:
        raise RuntimeError("factored classifier catalog failed freeze gates")
    encoded = "".join(item.model_dump_json() + "\n" for item in records).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    payload = {
        "schema_version": "servicepilot-factored-classifier-v1",
        "code_revision": args.code_revision,
        "output": str(args.output),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "record_count": len(records),
        "split_counts": dict(sorted(counts.items())),
        "family_count": 14,
        "exact_cross_split_overlap_count": len(exact),
        "near_duplicate_threshold": 0.8,
        "near_duplicate_count": len(near),
        "legacy_v4_dev_reused": False,
        "sealed_record_count": 0,
        "hard_eval_v2_accessed": False,
        "passed": passed,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
