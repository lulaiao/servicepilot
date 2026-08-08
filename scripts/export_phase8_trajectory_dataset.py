#!/usr/bin/env python3
"""Export privacy-safe trajectory JSONL with a reproducible data manifest."""

import argparse
import asyncio
import hashlib
from collections import Counter
from pathlib import Path

from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.training import (
    GENERATOR_VERSION,
    DataSplit,
    TrajectoryDatasetManifest,
    assign_family_splits,
    build_training_record,
    cross_split_overlap_count,
    deduplicate_records,
    family_hash,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("data/generated/phase8_trajectories.jsonl")
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("artifacts/reports/phase8_trajectory_manifest.json"),
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    scenarios = build_phase3_scenarios()
    family_splits = assign_family_splits(scenarios, seed=args.seed)
    harness = EvaluationHarness(code_revision=args.code_revision)
    raw_records = []
    for scenario in scenarios:
        trajectory, judge, _ = await harness.run_scenario(scenario)
        raw_records.append(
            build_training_record(
                scenario,
                trajectory,
                judge,
                split=family_splits[family_hash(scenario)],
            )
        )
    records = deduplicate_records(raw_records)
    encoded = "".join(record.model_dump_json() + "\n" for record in records).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    split_counts = Counter(record.split for record in records)
    split_families = {
        split: len({record.scenario_family_sha256 for record in records if record.split is split})
        for split in DataSplit
    }
    scenario_payload = b"\n".join(scenario.model_dump_json().encode() for scenario in scenarios)
    manifest = TrajectoryDatasetManifest(
        schema_version="servicepilot-trajectory-v1",
        generator_version=GENERATOR_VERSION,
        code_revision=args.code_revision,
        seed=args.seed,
        source_scenario_sha256=hashlib.sha256(scenario_payload).hexdigest(),
        output_sha256=hashlib.sha256(encoded).hexdigest(),
        raw_record_count=len(raw_records),
        deduplicated_record_count=len(records),
        duplicate_count=len(raw_records) - len(records),
        redaction_count=sum(record.redaction_count for record in records),
        split_counts={split: split_counts[split] for split in DataSplit},
        split_family_counts=split_families,
        cross_split_family_overlap_count=cross_split_overlap_count(
            records, "scenario_family_sha256"
        ),
        cross_split_content_overlap_count=cross_split_overlap_count(records, "content_sha256"),
    )
    if manifest.cross_split_family_overlap_count or manifest.cross_split_content_overlap_count:
        raise RuntimeError("cross-split leakage detected")
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(manifest.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
