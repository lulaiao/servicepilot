#!/usr/bin/env python3
"""Execute post-split variants and export canonical candidate trajectories."""

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.training import (
    ExpandedScenarioFamily,
    build_training_record,
    cross_split_overlap_count,
    deduplicate_records,
    expand_family_variants,
    near_duplicate_pairs,
    privacy_violation_count,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--sealed-catalog", type=Path, required=True)
    parser.add_argument("--train-dev-catalog", type=Path, required=True)
    parser.add_argument("--variant-output", type=Path, required=True)
    parser.add_argument("--trajectory-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.9)
    return parser.parse_args()


def load_families(path: Path) -> tuple[ExpandedScenarioFamily, ...]:
    return tuple(
        ExpandedScenarioFamily.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


async def main() -> None:
    args = parse_args()
    families = load_families(args.sealed_catalog) + load_families(args.train_dev_catalog)
    variants = tuple(variant for family in families for variant in expand_family_variants(family))
    variant_payload = "".join(item.model_dump_json() + "\n" for item in variants).encode()
    harness = EvaluationHarness(code_revision=args.code_revision)
    raw_records = []
    failures = []
    for variant in variants:
        trajectory, judge, _ = await harness.run_scenario(variant.scenario)
        if not judge.task_success:
            failures.append(
                {
                    "variant_id": variant.variant_id,
                    "failure_reasons": judge.failure_reasons,
                }
            )
            continue
        record = build_training_record(
            variant.scenario,
            trajectory,
            judge,
            split=variant.split,
        ).model_copy(update={"scenario_family_sha256": variant.semantic_signature_sha256})
        raw_records.append(record)
    records = deduplicate_records(raw_records)
    trajectory_payload = "".join(item.model_dump_json() + "\n" for item in records).encode()
    near_duplicates = near_duplicate_pairs(records, threshold=args.near_duplicate_threshold)
    privacy_violations = privacy_violation_count([item.model_dump(mode="json") for item in records])
    split_counts = Counter(item.split.value for item in records)
    split_family_counts = {
        split: len({item.scenario_family_sha256 for item in records if item.split.value == split})
        for split in ("train", "dev", "sealed_test")
    }
    payload = {
        "experiment": "phase9_expanded_trajectory_candidates_v1",
        "code_revision": args.code_revision,
        "family_count": len(families),
        "variant_count": len(variants),
        "successful_variant_count": len(raw_records),
        "failed_variant_count": len(failures),
        "deduplicated_record_count": len(records),
        "duplicate_count": len(raw_records) - len(records),
        "split_counts": dict(sorted(split_counts.items())),
        "split_family_counts": split_family_counts,
        "cross_split_family_overlap_count": cross_split_overlap_count(
            records, "scenario_family_sha256"
        ),
        "cross_split_content_overlap_count": cross_split_overlap_count(records, "content_sha256"),
        "near_duplicate_threshold": args.near_duplicate_threshold,
        "cross_split_near_duplicate_count": len(near_duplicates),
        "privacy_violation_count": privacy_violations,
        "variant_output": str(args.variant_output),
        "variant_output_sha256": hashlib.sha256(variant_payload).hexdigest(),
        "trajectory_output": str(args.trajectory_output),
        "trajectory_output_sha256": hashlib.sha256(trajectory_payload).hexdigest(),
        "admission_passed": not (
            failures
            or privacy_violations
            or near_duplicates
            or cross_split_overlap_count(records, "scenario_family_sha256")
            or cross_split_overlap_count(records, "content_sha256")
        ),
        "failures": failures,
        "near_duplicate_pairs": near_duplicates,
    }
    for path, data in (
        (args.variant_output, variant_payload),
        (args.trajectory_output, trajectory_payload),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in payload.items()
                if key not in {"failures", "near_duplicate_pairs"}
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
