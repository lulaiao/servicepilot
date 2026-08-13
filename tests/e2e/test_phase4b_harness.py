import asyncio
from pathlib import Path

import pytest

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.harness.evaluation_manifest import (
    EvaluationTrialStatus,
    JsonEvaluationManifestStore,
)
from servicepilot.harness.models import (
    HarnessSessionStatus,
    HarnessTerminationReason,
)


class IsolatedFlakyAgent(RoutedRuleAgent):
    calls: dict[str, int] = {}
    fail_scenario_id: str = ""

    async def run(self, scenario, simulator, gateway):  # type: ignore[no-untyped-def]
        self.calls[scenario.scenario_id] = self.calls.get(scenario.scenario_id, 0) + 1
        if scenario.scenario_id == self.fail_scenario_id and self.calls[scenario.scenario_id] == 1:
            raise RuntimeError("injected isolated trial failure")
        return await super().run(scenario, simulator, gateway)


class ConcurrencyTrackingAgent(RoutedRuleAgent):
    active = 0
    peak = 0

    async def run(self, scenario, simulator, gateway):  # type: ignore[no-untyped-def]
        type(self).active += 1
        type(self).peak = max(type(self).peak, type(self).active)
        try:
            await asyncio.sleep(0.01)
            return await super().run(scenario, simulator, gateway)
        finally:
            type(self).active -= 1


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
        and [event.sequence for event in session.events] == list(range(len(session.events)))
        for session in harness.sessions.values()
    )


@pytest.mark.asyncio
async def test_resumable_manifest_isolates_failure_and_skips_completed_trials(
    tmp_path: Path,
) -> None:
    scenarios = build_phase3_scenarios()[:3]
    IsolatedFlakyAgent.calls = {}
    IsolatedFlakyAgent.fail_scenario_id = scenarios[1].scenario_id
    store = JsonEvaluationManifestStore(tmp_path / "evaluation.json")
    harness = EvaluationHarness(code_revision="resumable-test")

    first = await harness.run_suite_resumable(
        scenarios,
        manifest_id="phase4b-resume",
        manifest_store=store,
        agent_factory=IsolatedFlakyAgent,
        max_concurrency=2,
    )

    assert first.completed_count == 2
    assert first.failed_count == 1
    assert store.load() == first

    resumed = await harness.run_suite_resumable(
        scenarios,
        manifest_id="phase4b-resume",
        manifest_store=store,
        agent_factory=IsolatedFlakyAgent,
        max_concurrency=2,
    )

    assert resumed.completed_count == 3
    assert resumed.failed_count == 0
    attempts = {item.scenario_id: item.attempts for item in resumed.records}
    assert attempts[scenarios[1].scenario_id] == 2
    assert attempts[scenarios[0].scenario_id] == 1
    assert attempts[scenarios[2].scenario_id] == 1
    assert sum(IsolatedFlakyAgent.calls.values()) == 4
    assert all(item.status is EvaluationTrialStatus.COMPLETED for item in resumed.records)


@pytest.mark.asyncio
async def test_evaluation_concurrency_is_bounded(tmp_path: Path) -> None:
    scenarios = build_phase3_scenarios()[:4]
    ConcurrencyTrackingAgent.active = 0
    ConcurrencyTrackingAgent.peak = 0
    harness = EvaluationHarness(code_revision="concurrency-test")

    manifest = await harness.run_suite_resumable(
        scenarios,
        manifest_id="phase4b-concurrency",
        manifest_store=JsonEvaluationManifestStore(tmp_path / "bounded.json"),
        agent_factory=ConcurrencyTrackingAgent,
        max_concurrency=2,
    )

    assert manifest.completed_count == 4
    assert manifest.failed_count == 0
    assert ConcurrencyTrackingAgent.peak == 2
