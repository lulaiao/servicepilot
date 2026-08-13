#!/usr/bin/env python3
"""Run the four deterministic Phase 4B Harness ablations."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.models import Intent
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.harness.evaluation import (
    EvaluationHarness,
    build_trial_environment,
)
from servicepilot.harness.guardrails import (
    GuardrailPipeline,
    PromptInjectionInputGuardrail,
)
from servicepilot.harness.models import HarnessBudgets, HarnessRunConfig
from servicepilot.harness.runtime import AgentRuntimeHarness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/phase4b_harness_ablations.json"),
    )
    return parser.parse_args()


def report_metrics(report: object) -> dict[str, Any]:
    payload = report.model_dump(mode="json")  # type: ignore[attr-defined]
    return {
        key: payload[key]
        for key in (
            "scenario_count",
            "task_success_count",
            "executable_task_success_rate",
            "final_state_accuracy",
            "policy_violation_rate",
            "false_success_rate",
            "average_turns",
            "average_tool_calls",
        )
    }


async def run(args: argparse.Namespace) -> None:
    scenarios = build_phase3_scenarios()
    scenario_bytes = b"\n".join(item.model_dump_json().encode() for item in scenarios)
    baseline_harness = EvaluationHarness(code_revision=args.code_revision)
    baseline_trajectories, baseline_results, baseline_report = await baseline_harness.run_suite(
        scenarios, agent_factory=RoutedRuleAgent
    )

    constrained = EvaluationHarness(
        code_revision=args.code_revision,
        budgets=HarnessBudgets(
            max_turns=24,
            max_tool_calls=1,
            max_retries=2,
            timeout_seconds=0.1,
        ),
    )
    _, _, constrained_report = await constrained.run_suite(scenarios, agent_factory=RoutedRuleAgent)

    no_reroute = EvaluationHarness(code_revision=args.code_revision)
    no_reroute_trajectories, _, no_reroute_report = await no_reroute.run_suite(
        scenarios,
        agent_factory=lambda: RoutedRuleAgent(observation_rerouting=False),
    )
    baseline_reroutes = sum(
        event.kind == "reroute_after_observation"
        for trajectory in baseline_trajectories
        for event in trajectory.events
    )
    ablated_reroutes = sum(
        event.kind == "reroute_after_observation"
        for trajectory in no_reroute_trajectories
        for event in trajectory.events
    )

    injection_scenarios = tuple(
        scenario
        for scenario in scenarios
        if scenario.intent is Intent.OUT_OF_SCOPE
        and ("忽略规则" in scenario.user_utterance or "直接修改数据库" in scenario.user_utterance)
    )
    blocked_sessions = 0
    blocked_tool_steps = 0
    for scenario in injection_scenarios:
        budgets = HarnessBudgets(timeout_seconds=0.1)
        environment = build_trial_environment(scenario, budgets)
        config = HarnessRunConfig(
            code_revision=args.code_revision,
            scenario_sha256=hashlib.sha256(scenario.model_dump_json().encode()).hexdigest(),
            budgets=budgets,
        )
        runtime = AgentRuntimeHarness(
            guardrails=GuardrailPipeline((PromptInjectionInputGuardrail(),))
        )
        session = await runtime.run(
            scenario=scenario,
            agent=RoutedRuleAgent(),
            simulator=FSMUserSimulator(scenario),
            gateway=environment.gateway,
            config=config,
        )
        blocked_sessions += int(session.trajectory is None)
        blocked_tool_steps += len(session.tool_steps)

    claim_only_acceptance = tuple(
        trajectory.claimed_success for trajectory in baseline_trajectories
    )
    authoritative_acceptance = tuple(result.task_success for result in baseline_results)
    verifier_disagreements = sum(
        claim != authoritative
        for claim, authoritative in zip(
            claim_only_acceptance, authoritative_acceptance, strict=True
        )
    )

    payload = {
        "code_revision": args.code_revision,
        "scenario_count": len(scenarios),
        "scenario_sha256": hashlib.sha256(scenario_bytes).hexdigest(),
        "judge": "DeterministicJudge",
        "baseline": report_metrics(baseline_report),
        "ablations": {
            "tool_budget": {
                "baseline_max_tool_calls": 12,
                "ablated_max_tool_calls": 1,
                "ablated": report_metrics(constrained_report),
                "success_rate_delta": round(
                    constrained_report.executable_task_success_rate
                    - baseline_report.executable_task_success_rate,
                    4,
                ),
            },
            "input_guardrail": {
                "targeted_injection_scenarios": len(injection_scenarios),
                "enabled_blocked_before_agent": blocked_sessions,
                "enabled_tool_steps": blocked_tool_steps,
                "disabled_authoritative_safe_outcomes": sum(
                    result.task_success
                    for scenario, result in zip(scenarios, baseline_results, strict=True)
                    if scenario in injection_scenarios
                ),
                "interpretation": (
                    "The Agent policy is a redundant second deterministic injection boundary."
                ),
            },
            "observation_rerouting": {
                "baseline_reroute_events": baseline_reroutes,
                "ablated_reroute_events": ablated_reroutes,
                "ablated": report_metrics(no_reroute_report),
                "success_rate_delta": round(
                    no_reroute_report.executable_task_success_rate
                    - baseline_report.executable_task_success_rate,
                    4,
                ),
            },
            "external_verifier": {
                "authoritative_success_count": sum(authoritative_acceptance),
                "agent_claim_only_accept_count": sum(claim_only_acceptance),
                "decision_disagreements": verifier_disagreements,
                "claim_only_false_rejections": sum(
                    authoritative and not claim
                    for claim, authoritative in zip(
                        claim_only_acceptance,
                        authoritative_acceptance,
                        strict=True,
                    )
                ),
                "interpretation": "Agent prose cannot replace authoritative state grading.",
            },
        },
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
