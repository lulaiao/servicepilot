#!/usr/bin/env python3
"""Export corrected executable-contract classifier SFT v3 data."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.training import (
    DataSplit,
    ExpandedScenarioVariant,
    build_contract_hard_negative_sft,
    build_failure_remediation_sft,
    to_classifier_sft,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
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
    base = tuple(
        to_classifier_sft(item).model_copy(
            update={"schema_version": "servicepilot-classifier-sft-v3-contract"}
        )
        for item in variants
    )
    legacy_remediation = tuple(
        item.model_copy(update={"schema_version": "servicepilot-classifier-sft-v3-contract"})
        for item in build_failure_remediation_sft(variants)
    )
    contract_remediation = build_contract_hard_negative_sft(variants)
    records = base + legacy_remediation + contract_remediation
    if len({item.record_id for item in records}) != len(records):
        raise RuntimeError("classifier SFT v3 record IDs are not unique")
    split_counts = Counter(item.split.value for item in records)
    expected = {"train": 804, "dev": 150, "sealed_test": 120}
    if split_counts != expected:
        raise RuntimeError(f"unexpected split counts: {split_counts}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(item.model_dump_json() + "\n" for item in records), encoding="utf-8"
    )
    payload = {
        "schema_version": "servicepilot-classifier-sft-v3-contract",
        "code_revision": args.code_revision,
        "source": str(args.variants),
        "source_sha256": sha256(args.variants),
        "output": str(args.output),
        "output_sha256": sha256(args.output),
        "record_count": len(records),
        "base_record_count": len(base),
        "legacy_train_remediation_count": len(legacy_remediation),
        "contract_hard_negative_count": len(contract_remediation),
        "contract_hard_negative_split_counts": {"train": 48, "dev": 24},
        "split_counts": dict(sorted(split_counts.items())),
        "sealed_hard_negative_count": sum(
            item.split is DataSplit.SEALED_TEST for item in contract_remediation
        ),
        "hard_eval_v2_accessed": False,
        "passed": True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
