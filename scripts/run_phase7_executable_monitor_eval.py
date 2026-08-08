#!/usr/bin/env python3
"""Run the frozen Phase 7B Monitor workload on real Harness trajectories."""

import argparse
import asyncio
import hashlib
import json
import random
import statistics
import time
from pathlib import Path

from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.monitoring import (
    PHASE7_FAULT_PROFILES,
    AsyncMonitor,
    DeterministicMonitor,
    inject_monitor_faults,
    observation_from_run,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory-count", type=int, default=1008)
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def repository_fingerprint(repository: object, scenario: object) -> str:
    payload = {
        "order": repr(repository.get_order(scenario.order_id)),
        "refunds": [repr(item) for item in repository.list_refunds(scenario.order_id)],
        "audits": [repr(item) for item in repository.list_audit_events()],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


async def main() -> None:
    args = parse_args()
    if args.trajectory_count < 1000:
        raise ValueError("Phase 7B requires at least 1000 executable trajectories")
    scenarios = build_phase3_scenarios()
    schedule = [
        (
            scenarios[index % len(scenarios)],
            PHASE7_FAULT_PROFILES[index % len(PHASE7_FAULT_PROFILES)],
        )
        for index in range(args.trajectory_count)
    ]
    random.Random(args.seed).shuffle(schedule)
    monitor = DeterministicMonitor()
    async_monitor = AsyncMonitor(max_queue_size=1)
    true_positive = false_positive = false_negative = 0
    sync_latencies: list[float] = []
    async_latencies: list[float] = []
    parity_failures = state_mutations = 0
    task_successes = 0
    natural_fault_trajectories = successful_recoveries = 0
    records: list[dict[str, object]] = []
    harness_started = time.perf_counter()
    for index, (scenario, injected_faults) in enumerate(schedule):
        harness = EvaluationHarness(code_revision=args.code_revision)
        trajectory, judge, repository = await harness.run_scenario(scenario)
        session = next(iter(harness.sessions.values()))
        task_successes += int(judge.task_success)
        base = observation_from_run(session, trajectory, judge)
        baseline_faults = {item.fault_class for item in monitor.evaluate(base).findings}
        natural_fault_seen = base.retries_used > 0 or bool(base.tool_error_codes)
        if natural_fault_seen:
            natural_fault_trajectories += 1
            successful_recoveries += int(judge.task_success)
        gold = baseline_faults | set(injected_faults)
        current = inject_monitor_faults(
            base,
            injected_faults,
            scenario_id=f"phase7b-{index:04d}-{scenario.scenario_id}",
        )
        before = repository_fingerprint(repository, scenario)
        started = time.perf_counter_ns()
        sync_report = monitor.evaluate(current)
        sync_latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        started = time.perf_counter_ns()
        await async_monitor.submit(current)
        async_report = await async_monitor.process_one()
        async_latencies.append((time.perf_counter_ns() - started) / 1_000_000)
        after = repository_fingerprint(repository, scenario)
        state_mutations += int(before != after)
        sync_found = {item.fault_class for item in sync_report.findings}
        async_found = {item.fault_class for item in async_report.findings}
        parity_failures += int(sync_found != async_found)
        true_positive += len(sync_found & gold)
        false_positive += len(sync_found - gold)
        false_negative += len(gold - sync_found)
        records.append(
            {
                "workload_id": current.scenario_id,
                "base_scenario_id": scenario.scenario_id,
                "injected": sorted(item.value for item in injected_faults),
                "natural_monitor_findings": sorted(item.value for item in baseline_faults),
                "natural_retry_count": base.retries_used,
                "gold": sorted(item.value for item in gold),
                "predicted": sorted(item.value for item in sync_found),
                "task_success": judge.task_success,
            }
        )
    harness_seconds = time.perf_counter() - harness_started
    precision = true_positive / (true_positive + false_positive)
    recall = true_positive / (true_positive + false_negative)
    payload = {
        "experiment": "phase7_executable_monitor_eval",
        "code_revision": args.code_revision,
        "seed": args.seed,
        "trajectory_count": args.trajectory_count,
        "base_scenario_count": len(scenarios),
        "fault_profile_count": len(PHASE7_FAULT_PROFILES),
        "method": "real Harness execution followed by seeded redacted-boundary fault injection",
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "sync_async_parity_rate": round(1 - parity_failures / args.trajectory_count, 4),
            "monitor_state_mutation_count": state_mutations,
            "authoritative_task_success_rate": round(task_successes / args.trajectory_count, 4),
            "natural_fault_trajectory_count": natural_fault_trajectories,
            "successful_recovery_count": successful_recoveries,
            "mean_sync_monitor_latency_ms": round(statistics.mean(sync_latencies), 4),
            "p95_sync_monitor_latency_ms": round(
                sorted(sync_latencies)[int(len(sync_latencies) * 0.95) - 1], 4
            ),
            "mean_async_roundtrip_latency_ms": round(statistics.mean(async_latencies), 4),
            "harness_and_monitor_wall_seconds": round(harness_seconds, 4),
        },
        "schedule_sha256": hashlib.sha256(
            json.dumps(
                [
                    (item.scenario_id, sorted(fault.value for fault in faults))
                    for item, faults in schedule
                ],
                ensure_ascii=False,
            ).encode()
        ).hexdigest(),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
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
