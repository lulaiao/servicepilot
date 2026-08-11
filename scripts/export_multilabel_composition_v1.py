#!/usr/bin/env python3
"""Freeze and audit family-split multi-label composition pilot data."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.training.multilabel_composition_data import build_multilabel_composition_v1


def shingles(text: str, size: int = 5) -> set[str]:
    value = "".join(text.lower().split())
    return {value[index : index + size] for index in range(max(1, len(value) - size + 1))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    records = build_multilabel_composition_v1()
    train = tuple(item for item in records if item.split == "train")
    dev = tuple(item for item in records if item.split == "dev")
    train_families = {item.family_id for item in train}
    dev_families = {item.family_id for item in dev}
    exact_overlap = {item.text for item in train} & {item.text for item in dev}
    signature_overlap = {item.semantic_signature_sha256 for item in train} & {
        item.semantic_signature_sha256 for item in dev
    }
    near_pairs = []
    for left in train:
        left_value = shingles(left.text)
        for right in dev:
            right_value = shingles(right.text)
            score = len(left_value & right_value) / len(left_value | right_value)
            if score >= 0.8:
                near_pairs.append((left.record_id, right.record_id, round(score, 4)))
    passed = (
        len(records) == 240
        and len(train) == 192
        and len(dev) == 48
        and not train_families & dev_families
        and not exact_overlap
        and not signature_overlap
        and not near_pairs
        and len({item.record_id for item in records}) == len(records)
    )
    if not passed:
        raise RuntimeError("multi-label composition v1 failed freeze gates")
    encoded = "".join(item.model_dump_json() + "\n" for item in records).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    payload = {
        "schema_version": "servicepilot-multilabel-composition-v1-manifest",
        "code_revision_before_freeze": args.code_revision,
        "output": str(args.output),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "record_count": len(records),
        "split_counts": {"train": len(train), "dev": len(dev), "sealed_test": 0},
        "family_counts": {"train": len(train_families), "dev": len(dev_families)},
        "category_counts": dict(sorted(Counter(item.category for item in records).items())),
        "label_positive_counts": dict(sorted(Counter(label.value for item in records for label in item.labels).items())),
        "exact_cross_split_overlap_count": len(exact_overlap),
        "semantic_signature_cross_split_overlap_count": len(signature_overlap),
        "near_duplicate_threshold": 0.8,
        "near_duplicate_cross_split_count": len(near_pairs),
        "split_unit": "semantic_family",
        "sealed_record_count": 0,
        "passed": passed,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
