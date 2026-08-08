#!/usr/bin/env python3
"""Compare the legacy direct loop with the formalized Harness boundary."""

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.judge import DeterministicJudge
from servicepilot.eval.models import JudgeResult, Trajectory
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.harness.evaluation import (
    EvaluationHarness,
    build_report,
    build_trial_environment,
)
from servicepilot.harness.models import HarnessBudgets, ReplayMode
from servicepilot.harness.runtime import AgentRuntimeHarness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/phase4b_harness_comparison.json"),
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=Path("artifacts/traces/phase4b_harness_trajectories.jsonl"),
    )
    return parser.parse_args()


async def run_direct(
    budgets: HarnessBudgets,
) -> tuple[tuple[Trajectory, ...], tuple[JudgeResult, ...], float]:
    trajectories: list[Trajectory] = []
    results: list[JudgeResult] = []
    scenarios = build_phase3_scenarios()
    started = time.perf_counter()
    for scenario in scenarios:
        environment = build_trial_environment(scenario, budgets)
        trajectory = await RoutedRuleAgent().run(
            scenario,
            FSMUserSimulator(scenario),
            environment.gateway,
        )
        result = DeterministicJudge().evaluate(
            scenario, trajectory, environment.repository
        )
        trajectories.append(trajectory)
        results.append(result)
    return tuple(trajectories), tuple(results), time.perf_counter() - started


async def main_async() -> None:
    args = parse_args()
    scenarios = build_phase3_scenarios()
    budgets = HarnessBudgets(timeout_seconds=0.1)
    direct_trajectories, direct_results, direct_elapsed = await run_direct(
        budgets
    )
    harness = EvaluationHarness(
        code_revision=args.code_revision,
        budgets=budgets,
    )
    started = time.perf_counter()
    harness_trajectories, harness_results, harness_report = (
        await harness.run_suite(scenarios, agent_factory=RoutedRuleAgent)
    )
    harness_elapsed = time.perf_counter() - started
    direct_report = build_report(scenarios, list(direct_results))
    replay_runtime = AgentRuntimeHarness()
    replay_sessions = []
    for scenario, trajectory, session in zip(
        scenarios,
        harness_trajectories,
        harness.sessions.values(),
        strict=True,
    ):
        replay_sessions.append(
            replay_runtime.replay(
                trajectory=trajectory,
                scenario=scenario,
                config=session.config,
                mode=ReplayMode.VERIFY_ONLY,
            )
        )
    scenario_bytes = b"\n".join(
        item.model_dump_json().encode() for item in scenarios
    )
    identical_judgments = all(
        direct.model_dump() == formal.model_dump()
        for direct, formal in zip(
            direct_results, harness_results, strict=True
        )
    )
    payload = {
        "code_revision": args.code_revision,
        "scenario_count": len(scenarios),
        "scenario_sha256": hashlib.sha256(scenario_bytes).hexdigest(),
        "budgets": budgets.model_dump(mode="json"),
        "direct_loop": {
            "elapsed_seconds": round(direct_elapsed, 6),
            "report": direct_report.model_dump(mode="json"),
        },
        "formal_harness": {
            "elapsed_seconds": round(harness_elapsed, 6),
            "report": harness_report.model_dump(mode="json"),
            "session_count": len(harness.sessions),
            "event_count": sum(
                len(item.events) for item in harness.sessions.values()
            ),
            "replay_session_count": len(replay_sessions),
        },
        "identical_judgments": identical_judgments,
        "absolute_overhead_seconds": round(
            harness_elapsed - direct_elapsed, 6
        ),
        "mean_overhead_milliseconds_per_scenario": round(
            (harness_elapsed - direct_elapsed) * 1000 / len(scenarios), 4
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.trace_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.trace_output.write_text(
        "\n".join(item.model_dump_json() for item in harness_trajectories)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
