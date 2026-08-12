#!/usr/bin/env python3
"""Freeze the independently authored multi-label holdout without model inference."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.eval.multilabel_holdout_v1 import build_multilabel_holdout_v1
from servicepilot.training.multilabel_composition_data import MultiLabelCompositionRecord


def normalized(text: str) -> str:
    return "".join(character.lower() for character in text if not character.isspace())


def shingles(text: str, size: int = 5) -> set[str]:
    value = normalized(text)
    return {value[index : index + size] for index in range(max(1, len(value) - size + 1))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-data", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    cases = build_multilabel_holdout_v1()
    training = tuple(
        MultiLabelCompositionRecord.model_validate_json(line)
        for line in args.training_data.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    train_texts = {normalized(item.text) for item in training}
    exact_overlap = [case.case_id for case in cases if normalized(case.text) in train_texts]
    training_shingles = [(item.record_id, shingles(item.text)) for item in training]
    nearest = []
    for case in cases:
        current = shingles(case.text)
        record_id, score = max(
            (
                (record_id, len(current & candidate) / len(current | candidate))
                for record_id, candidate in training_shingles
            ),
            key=lambda pair: pair[1],
        )
        nearest.append({"case_id": case.case_id, "record_id": record_id, "score": score})
    max_similarity = max(item["score"] for item in nearest)
    if exact_overlap or max_similarity >= 0.8:
        raise RuntimeError(
            f"holdout leakage gate failed: exact={exact_overlap}, max_similarity={max_similarity}"
        )
    encoded = "".join(case.model_dump_json() + "\n" for case in cases).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    label_counts = Counter(label.value for case in cases for label in case.labels)
    payload = {
        "schema_version": "servicepilot-multilabel-holdout-v1-freeze",
        "provenance": "post_selection_independent_manual_authoring",
        "code_revision_before_freeze": args.code_revision,
        "catalog": str(args.output),
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "training_data": str(args.training_data),
        "training_data_sha256": hashlib.sha256(args.training_data.read_bytes()).hexdigest(),
        "protocol": str(args.protocol),
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "case_count": len(cases),
        "category_counts": dict(sorted(Counter(case.category for case in cases).items())),
        "label_positive_counts": dict(sorted(label_counts.items())),
        "normalized_exact_overlap_count": len(exact_overlap),
        "max_cross_dataset_character_5gram_similarity": round(max_similarity, 4),
        "near_duplicate_threshold": 0.8,
        "model_inference_executed": False,
        "head_weights_accessed": False,
        "selection_or_tuning_allowed": False,
        "threshold": protocol["threshold"],
        "acceptance_gates": {
            "required_seed_pass_count": protocol["required_seed_pass_count"],
            **protocol["acceptance_gates"],
        },
        "rerun_allowed": False,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
