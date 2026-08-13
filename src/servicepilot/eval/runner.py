"""Compatibility wrappers backed by the formal Evaluation Harness."""

from collections.abc import Callable

from servicepilot.agents.rule_baseline import RuleBasedSingleAgent
from servicepilot.domain.repositories import InMemoryRepository
from servicepilot.eval.models import (
    EvalReport,
    JudgeResult,
    ScenarioSpec,
    Trajectory,
)
from servicepilot.harness.evaluation import (
    EvaluationHarness,
    build_report,
)


async def run_scenario(
    scenario: ScenarioSpec,
    agent: RuleBasedSingleAgent | None = None,
) -> tuple[Trajectory, JudgeResult, InMemoryRepository]:
    return await EvaluationHarness().run_scenario(scenario, agent=agent)


async def run_suite(
    scenarios: tuple[ScenarioSpec, ...],
    agent_factory: Callable[[], RuleBasedSingleAgent] = RuleBasedSingleAgent,
) -> tuple[tuple[Trajectory, ...], tuple[JudgeResult, ...], EvalReport]:
    return await EvaluationHarness().run_suite(scenarios, agent_factory=agent_factory)


__all__ = ["build_report", "run_scenario", "run_suite"]
