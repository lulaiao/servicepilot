#!/usr/bin/env python3
"""Export the deployment-aligned classifier SFT v2 view and its audit report."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.training import (
    DataSplit,
    ExpandedScenarioVariant,
    build_failure_remediation_sft,
    to_classifier_sft,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    args = parse_args()
    variants = tuple(
        ExpandedScenarioVariant.model_validate_json(line)
        for line in args.variants.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    base_records = tuple(to_classifier_sft(item) for item in variants)
    remediation = build_failure_remediation_sft(variants)
    records = base_records + remediation
    if len({item.record_id for item in records}) != len(records):
        raise RuntimeError("classifier SFT record IDs are not unique")
    split_counts = Counter(item.split.value for item in records)
    family_owners: dict[str, set[str]] = {}
    for variant in variants:
        family_owners.setdefault(variant.family_id, set()).add(variant.split.value)
    overlap = sum(len(owners) > 1 for owners in family_owners.values())
    if overlap:
        raise RuntimeError("classifier view contains cross-split family leakage")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(item.model_dump_json() + "\n" for item in records), encoding="utf-8"
    )
    payload = {
        "schema_version": "servicepilot-classifier-sft-v2",
        "source": str(args.variants),
        "source_sha256": sha256(args.variants),
        "output": str(args.output),
        "output_sha256": sha256(args.output),
        "record_count": len(records),
        "base_record_count": len(base_records),
        "train_only_remediation_record_count": len(remediation),
        "split_counts": dict(sorted(split_counts.items())),
        "cross_split_family_overlap_count": overlap,
        "message_count_per_record": sorted({len(item.messages) for item in records}),
        "sealed_train_access_allowed": False,
        "passed": split_counts
        == {
            DataSplit.TRAIN.value: 756,
            DataSplit.DEV.value: 126,
            DataSplit.SEALED_TEST.value: 120,
        },
    }
    if not payload["passed"]:
        raise RuntimeError(f"unexpected split counts: {split_counts}")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
