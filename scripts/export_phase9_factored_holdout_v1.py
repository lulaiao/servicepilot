#!/usr/bin/env python3
"""Freeze the post-rule one-shot factored holdout and its integrity evidence."""

import argparse
import hashlib
import json
from pathlib import Path

from servicepilot.eval.factored_holdout_v1 import build_factored_holdout_v1
from servicepilot.training.data_models import SFTTrainingRecord


def text(record: SFTTrainingRecord) -> str:
    return record.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1]


def shingles(value: str, size: int = 5) -> set[str]:
    normalized = "".join(value.lower().split())
    return {normalized[index : index + size] for index in range(max(1, len(normalized) - size + 1))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--rule-revision", required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    holdout = build_factored_holdout_v1()
    development = tuple(
        SFTTrainingRecord.model_validate_json(line)
        for line in args.development_dataset.read_text().splitlines()
        if line.strip()
    )
    exact = {text(item) for item in holdout} & {text(item) for item in development}
    near = []
    for left in holdout:
        left_shingles = shingles(text(left))
        for right in development:
            right_shingles = shingles(text(right))
            score = len(left_shingles & right_shingles) / len(left_shingles | right_shingles)
            if score >= 0.8:
                near.append(
                    {
                        "holdout_id": left.record_id,
                        "development_id": right.record_id,
                        "score": round(score, 4),
                    }
                )
    if exact or near or len(holdout) != 24:
        raise RuntimeError("holdout integrity freeze failed")
    encoded = "".join(item.model_dump_json() + "\n" for item in holdout).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    payload = {
        "schema_version": "servicepilot-factored-holdout-v1",
        "code_revision": args.code_revision,
        "rules_frozen_before_authoring_at_revision": args.rule_revision,
        "output": str(args.output),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "record_count": len(holdout),
        "split_counts": {"sealed_test": len(holdout)},
        "exact_development_overlap_count": len(exact),
        "near_duplicate_threshold": 0.8,
        "near_duplicate_count": len(near),
        "one_shot_execution": True,
        "retuning_or_reexecution_after_observation_allowed": False,
        "hard_eval_v2_accessed": False,
        "passed": True,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
