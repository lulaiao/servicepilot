#!/usr/bin/env python3
"""Export and freeze the balanced train-only multi-label v2 dataset."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.training.multilabel_composition_v2_data import (
    build_multilabel_composition_v2,
)


def shingles(text: str, size: int = 5) -> set[str]:
    value = "".join(text.lower().split())
    return {value[index : index + size] for index in range(max(1, len(value) - size + 1))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    records = build_multilabel_composition_v2()
    train = tuple(item for item in records if item.split == "train")
    dev = tuple(item for item in records if item.split == "dev")
    train_text = {item.text for item in train}
    exact_overlap = sum(item.text in train_text for item in dev)
    train_signatures = {item.semantic_signature_sha256 for item in train}
    signature_overlap = sum(item.semantic_signature_sha256 in train_signatures for item in dev)
    train_shingles = [(item.record_id, shingles(item.text)) for item in train]
    max_similarity = max(
        max(len(current & candidate) / len(current | candidate) for _, candidate in train_shingles)
        for current in (shingles(item.text) for item in dev)
    )
    if exact_overlap or signature_overlap or max_similarity >= 0.8:
        raise RuntimeError("v2 family split leakage gate failed")
    encoded = "".join(item.model_dump_json() + "\n" for item in records).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    payload = {
        "schema_version": "servicepilot-multilabel-composition-v2-manifest",
        "code_revision_before_freeze": args.code_revision,
        "output": str(args.output),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "record_count": len(records),
        "family_count": len({item.family_id for item in records}),
        "split_counts": dict(sorted(Counter(item.split for item in records).items())),
        "split_family_counts": {
            split: len({item.family_id for item in records if item.split == split})
            for split in ("train", "dev")
        },
        "category_counts": dict(sorted(Counter(item.category for item in records).items())),
        "label_positive_counts": dict(
            sorted(Counter(label.value for item in records for label in item.labels).items())
        ),
        "label_prevalence": {
            label: round(count / len(records), 4)
            for label, count in sorted(
                Counter(label.value for item in records for label in item.labels).items()
            )
        },
        "exact_cross_split_overlap_count": exact_overlap,
        "semantic_signature_cross_split_overlap_count": signature_overlap,
        "max_cross_split_character_5gram_similarity": round(max_similarity, 4),
        "near_duplicate_threshold": 0.8,
        "split_unit": "semantic_family",
        "sealed_record_count": 0,
        "consumed_holdout_text_used": False,
        "passed": True,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
