import pytest

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.harness.models import (
    HarnessSessionStatus,
    HarnessTerminationReason,
)


@pytest.mark.asyncio
async def test_formal_evaluation_harness_preserves_all_phase3_outcomes() -> None:
    scenarios = build_phase3_scenarios()
    harness = EvaluationHarness(code_revision="phase4b-test")

    trajectories, results, report = await harness.run_suite(
        scenarios, agent_factory=RoutedRuleAgent
    )

    assert len(trajectories) == len(results) == len(harness.sessions) == 36
    assert report.executable_task_success_rate == 1.0
    assert report.final_state_accuracy == 1.0
    assert report.policy_violation_rate == 0.0
    assert report.false_success_rate == 0.0
    assert all(
        session.status is HarnessSessionStatus.COMPLETED
        and session.termination_reason is HarnessTerminationReason.COMPLETED
        and [event.sequence for event in session.events]
        == list(range(len(session.events)))
        for session in harness.sessions.values()
    )
