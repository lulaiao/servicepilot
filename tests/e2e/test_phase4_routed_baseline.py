import pytest

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.models import Intent
from servicepilot.eval.runner import run_scenario, run_suite


@pytest.mark.asyncio
async def test_routed_agent_records_dynamic_role_decisions() -> None:
    scenario = next(
        item
        for item in build_phase3_scenarios()
        if item.intent is Intent.MULTI_INTENT and item.accept_confirmation
    )

    trajectory, result, _ = await run_scenario(scenario, agent=RoutedRuleAgent())
    routes = [
        event.content
        for event in trajectory.events
        if event.kind in {"route", "reroute_after_observation"}
    ]

    assert result.task_success is True
    assert any("order_agent" in route for route in routes)
    assert any("escalation_agent" in route for route in routes)
    assert any("verifier" in route for route in routes)


@pytest.mark.asyncio
async def test_routed_agent_matches_single_agent_business_outcomes() -> None:
    scenarios = build_phase3_scenarios()

    _, results, report = await run_suite(scenarios, agent_factory=RoutedRuleAgent)

    assert len(results) == 36
    assert report.executable_task_success_rate == 1.0
    assert report.final_state_accuracy == 1.0
    assert report.policy_violation_rate == 0.0
    assert report.false_success_rate == 0.0
