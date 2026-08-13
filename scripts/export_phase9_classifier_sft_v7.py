#!/usr/bin/env python3
"""Freeze bounded v7 train-only remediation with immutable v4 dev."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.training.classifier_v4_catalog import build_classifier_v4_sft
from servicepilot.training.classifier_v7_data import build_classifier_v7_sft
from servicepilot.training.data_models import DataSplit, SFTTrainingRecord


def text(record: SFTTrainingRecord) -> str:
    return record.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()

    records = build_classifier_v7_sft()
    train = tuple(item for item in records if item.split is DataSplit.TRAIN)
    dev = tuple(item for item in records if item.split is DataSplit.DEV)
    new = tuple(item for item in train if item.source_record_id.startswith("v7-train-"))
    v4_dev = tuple(item for item in build_classifier_v4_sft() if item.split is DataSplit.DEV)
    exact_overlap = {text(item) for item in train} & {text(item) for item in dev}
    passed = (
        len(records) == 180
        and len(train) == 144
        and len(dev) == 36
        and len(new) == 24
        and not exact_overlap
        and dev == v4_dev
        and len({item.record_id for item in records}) == len(records)
    )
    if not passed:
        raise RuntimeError("classifier SFT v7 failed freeze gates")

    encoded = "".join(item.model_dump_json() + "\n" for item in records).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    categories = Counter(
        item.source_record_id.removeprefix("v7-train-").rsplit("-", maxsplit=1)[0] for item in new
    )
    payload = {
        "schema_version": "servicepilot-classifier-sft-v7-remediation",
        "code_revision_before_freeze": args.code_revision,
        "output": str(args.output),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "record_count": len(records),
        "split_counts": {"train": len(train), "dev": len(dev), "sealed_test": 0},
        "new_train_record_count": len(new),
        "new_train_category_counts": dict(sorted(categories.items())),
        "dev_sha256": hashlib.sha256(
            "".join(item.model_dump_json() + "\n" for item in dev).encode()
        ).hexdigest(),
        "dev_changed_from_v4": dev != v4_dev,
        "exact_train_dev_overlap_count": len(exact_overlap),
        "inherits_v6": False,
        "consumed_agent_sealed_v1_loaded": False,
        "sealed_record_count": 0,
        "passed": passed,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
