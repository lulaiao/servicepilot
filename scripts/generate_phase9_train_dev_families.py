#!/usr/bin/env python3
"""Generate and execute the first train/dev semantic-family batch."""

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.training import (
    ExpandedScenarioFamily,
    build_phase9_train_dev_families,
    build_phase9_train_dev_families_v2,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--sealed-catalog", type=Path, required=True)
    parser.add_argument("--reserved-catalog", type=Path, action="append", default=[])
    parser.add_argument("--batch-version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    reserved_paths = (args.sealed_catalog, *args.reserved_catalog)
    reserved = tuple(
        ExpandedScenarioFamily.model_validate_json(line)
        for path in reserved_paths
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    families = (
        build_phase9_train_dev_families(seed=args.seed)
        if args.batch_version == "v1"
        else build_phase9_train_dev_families_v2(seed=args.seed)
    )
    overlap = {item.semantic_signature_sha256 for item in reserved} & {
        item.semantic_signature_sha256 for item in families
    }
    if overlap:
        raise RuntimeError(f"train/dev collides with {len(overlap)} reserved signatures")
    encoded = "".join(item.model_dump_json() + "\n" for item in families).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    harness = EvaluationHarness(code_revision=args.code_revision)
    records = []
    for family in families:
        trajectory, judge, _ = await harness.run_scenario(family.canonical_scenario)
        records.append(
            {
                "family_id": family.family_id,
                "split": family.split.value,
                "task_success": judge.task_success,
                "false_success": judge.false_success,
                "policy_compliant": judge.policy_compliant,
                "failure_reasons": judge.failure_reasons,
                "trace_sha256": hashlib.sha256(trajectory.model_dump_json().encode()).hexdigest(),
            }
        )
    split_counts = Counter(item.split.value for item in families)
    fault_counts = Counter(item.dimensions["fault_profile"] for item in families)
    payload = {
        "experiment": f"phase9_train_dev_family_batch_{args.batch_version}",
        "batch_version": args.batch_version,
        "code_revision": args.code_revision,
        "seed": args.seed,
        "sealed_catalog": str(args.sealed_catalog),
        "sealed_catalog_sha256": hashlib.sha256(args.sealed_catalog.read_bytes()).hexdigest(),
        "reserved_catalogs": [str(path) for path in reserved_paths],
        "semantic_overlap_with_sealed": len(overlap),
        "family_count": len(families),
        "split_counts": dict(sorted(split_counts.items())),
        "fault_profile_counts": dict(sorted(fault_counts.items())),
        "catalog": str(args.output),
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "task_success_count": sum(item["task_success"] for item in records),
        "false_success_count": sum(item["false_success"] for item in records),
        "policy_violation_count": sum(not item["policy_compliant"] for item in records),
        "records": records,
    }
    if payload["task_success_count"] != len(families):
        raise RuntimeError("train/dev family execution gate failed")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: value for key, value in payload.items() if key != "records"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
