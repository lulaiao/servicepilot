#!/usr/bin/env python3
"""Freeze and execute the independently reserved Phase 9 sealed families."""

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.training import build_phase9_sealed_families


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    families = build_phase9_sealed_families()
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
                "semantic_signature_sha256": family.semantic_signature_sha256,
                "task_success": judge.task_success,
                "false_success": judge.false_success,
                "policy_compliant": judge.policy_compliant,
                "failure_reasons": judge.failure_reasons,
                "trace_sha256": hashlib.sha256(trajectory.model_dump_json().encode()).hexdigest(),
            }
        )
    profile_counts = Counter(item.dimensions["fault_profile"] for item in families)
    payload = {
        "experiment": "phase9_sealed_family_freeze",
        "code_revision": args.code_revision,
        "provenance": "independently_authored_phase9_sealed_v1",
        "family_count": len(families),
        "canonical_scenario_count": len(families),
        "catalog": str(args.output),
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "semantic_signature_manifest_sha256": hashlib.sha256(
            "\n".join(sorted(item.semantic_signature_sha256 for item in families)).encode()
        ).hexdigest(),
        "fault_profile_counts": dict(sorted(profile_counts.items())),
        "task_success_count": sum(item["task_success"] for item in records),
        "false_success_count": sum(item["false_success"] for item in records),
        "policy_violation_count": sum(not item["policy_compliant"] for item in records),
        "records": records,
        "decision": "sealed_families_frozen_before_train_dev_generation",
    }
    if payload["task_success_count"] != len(families):
        raise RuntimeError("sealed family execution gate failed")
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
