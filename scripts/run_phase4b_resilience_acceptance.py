#!/usr/bin/env python3
"""Run the durable, bounded-concurrency Phase 4B acceptance suite."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.harness.evaluation import EvaluationHarness, build_report
from servicepilot.harness.evaluation_manifest import JsonEvaluationManifestStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--max-concurrency", type=int, default=4)
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("artifacts/reports/phase4b_resumable_run.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/phase4b_resilience_acceptance.json"),
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    scenarios = build_phase3_scenarios()
    harness = EvaluationHarness(code_revision=args.code_revision)
    store = JsonEvaluationManifestStore(args.manifest_output)
    first = await harness.run_suite_resumable(
        scenarios,
        manifest_id="phase4b-resilience-acceptance",
        manifest_store=store,
        agent_factory=RoutedRuleAgent,
        max_concurrency=args.max_concurrency,
    )
    resumed = await harness.run_suite_resumable(
        scenarios,
        manifest_id="phase4b-resilience-acceptance",
        manifest_store=store,
        agent_factory=RoutedRuleAgent,
        max_concurrency=args.max_concurrency,
    )
    results = [
        record.judge_result
        for record in resumed.records
        if record.judge_result is not None
    ]
    report = build_report(scenarios, results)
    attempts_unchanged = [item.attempts for item in first.records] == [
        item.attempts for item in resumed.records
    ]
    payload = {
        "code_revision": args.code_revision,
        "scenario_count": len(scenarios),
        "scenario_sha256": hashlib.sha256(
            b"\n".join(item.model_dump_json().encode() for item in scenarios)
        ).hexdigest(),
        "max_concurrency": args.max_concurrency,
        "first_run": {
            "completed": first.completed_count,
            "failed": first.failed_count,
        },
        "resume": {
            "completed": resumed.completed_count,
            "failed": resumed.failed_count,
            "completed_trials_skipped": attempts_unchanged,
            "maximum_attempts": max(item.attempts for item in resumed.records),
        },
        "report": report.model_dump(mode="json"),
        "manifest_output": str(args.manifest_output),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
