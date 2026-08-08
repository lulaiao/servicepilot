#!/usr/bin/env python3
"""Derive provenance-safe SFT and preference views from canonical trajectories."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.training import (
    DataSplit,
    TrajectoryTrainingRecord,
    mine_hard_negatives,
    near_duplicate_pairs,
    privacy_violation_count,
    to_sft_record,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument(
        "--input", type=Path, default=Path("data/generated/phase8_trajectories.jsonl")
    )
    parser.add_argument("--sft-output", type=Path, default=Path("data/generated/phase8_sft.jsonl"))
    parser.add_argument(
        "--preference-output",
        type=Path,
        default=Path("data/generated/phase8_preferences.jsonl"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("artifacts/reports/phase8_training_views_manifest.json"),
    )
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.9)
    return parser.parse_args()


def encode_jsonl(records: tuple[object, ...]) -> bytes:
    return "".join(record.model_dump_json() + "\n" for record in records).encode()


def main() -> None:
    args = parse_args()
    canonical = tuple(
        TrajectoryTrainingRecord.model_validate_json(line)
        for line in args.input.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    sft = tuple(to_sft_record(record) for record in canonical)
    preferences = tuple(
        preference for record in canonical for preference in mine_hard_negatives(record)
    )
    near_duplicates = near_duplicate_pairs(canonical, threshold=args.near_duplicate_threshold)
    sft_payload = encode_jsonl(sft)
    preference_payload = encode_jsonl(preferences)
    privacy_violations = privacy_violation_count(
        [record.model_dump(mode="json") for record in (*sft, *preferences)]
    )
    if privacy_violations:
        raise RuntimeError(f"privacy scan found {privacy_violations} raw sensitive values")
    if near_duplicates:
        raise RuntimeError(f"cross-split near-duplicate audit found {len(near_duplicates)} pairs")
    for path, payload in (
        (args.sft_output, sft_payload),
        (args.preference_output, preference_payload),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    preference_split_counts = Counter(item.split for item in preferences)
    chosen_counts = Counter(item.chosen_tool for item in preferences)
    rejected_counts = Counter(item.rejected_tool for item in preferences)
    manifest = {
        "experiment": "phase8_training_views",
        "code_revision": args.code_revision,
        "canonical_input": str(args.input),
        "canonical_input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "sft": {
            "schema_version": "servicepilot-sft-v1",
            "record_count": len(sft),
            "output": str(args.sft_output),
            "output_sha256": hashlib.sha256(sft_payload).hexdigest(),
        },
        "preference": {
            "schema_version": "servicepilot-preference-v1",
            "record_count": len(preferences),
            "output": str(args.preference_output),
            "output_sha256": hashlib.sha256(preference_payload).hexdigest(),
            "split_counts": {split.value: preference_split_counts[split] for split in DataSplit},
            "chosen_tool_counts": dict(sorted(chosen_counts.items())),
            "rejected_tool_counts": dict(sorted(rejected_counts.items())),
        },
        "audits": {
            "privacy_violation_count": privacy_violations,
            "near_duplicate_threshold": args.near_duplicate_threshold,
            "cross_split_near_duplicate_count": len(near_duplicates),
            "missing_source_provenance_count": sum(
                not item.source_record_id for item in (*sft, *preferences)
            ),
            "chosen_equals_rejected_count": sum(
                item.chosen_tool == item.rejected_tool for item in preferences
            ),
        },
    }
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
