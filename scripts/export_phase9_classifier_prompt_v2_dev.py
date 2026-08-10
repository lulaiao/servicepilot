#!/usr/bin/env python3
"""Freeze a prompt-only dev diagnostic without changing utterances or targets."""

import argparse
import hashlib
import json
from pathlib import Path

from servicepilot.routing.structured_output import build_intent_prompt_v2
from servicepilot.training.classifier_v4_catalog import build_classifier_v4_sft
from servicepilot.training.data_models import DataSplit, SFTTrainingRecord


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = tuple(item for item in build_classifier_v4_sft() if item.split is DataSplit.DEV)
    records = []
    for item in source:
        utterance = item.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1]
        digest = hashlib.sha256(f"prompt-v2:{item.record_id}:{utterance}".encode()).hexdigest()
        records.append(
            SFTTrainingRecord(
                schema_version="servicepilot-classifier-prompt-contract-v2-dev",
                record_id=f"classifier-prompt-v2-{digest[:20]}",
                source_record_id=item.record_id,
                split=DataSplit.DEV,
                messages=(
                    {"role": "user", "content": build_intent_prompt_v2(utterance)},
                    item.messages[1],
                ),
            )
        )
    source_utterances = tuple(
        item.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1] for item in source
    )
    output_utterances = tuple(
        item.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1] for item in records
    )
    targets_unchanged = tuple(item.messages[1] for item in source) == tuple(
        item.messages[1] for item in records
    )
    passed = (
        len(records) == 36
        and source_utterances == output_utterances
        and targets_unchanged
        and len({item.record_id for item in records}) == len(records)
    )
    if not passed:
        raise RuntimeError("prompt contract v2 diagnostic failed its freeze gates")
    encoded = "".join(item.model_dump_json() + "\n" for item in records).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    payload = {
        "schema_version": "servicepilot-classifier-prompt-contract-v2-dev",
        "code_revision": args.code_revision,
        "output": str(args.output),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "record_count": len(records),
        "split_counts": {"dev": 36, "train": 0, "sealed_test": 0},
        "utterances_unchanged": source_utterances == output_utterances,
        "targets_unchanged": targets_unchanged,
        "model_weights_changed": False,
        "sealed_record_count": 0,
        "hard_eval_v2_accessed": False,
        "passed": passed,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
