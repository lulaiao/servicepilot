import hashlib

import pytest

from servicepilot.agents.rule_baseline import RuleBasedSingleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.models import Intent
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.harness.checkpoints import InMemoryCheckpointStore
from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.harness.guardrails import GuardrailPipeline
from servicepilot.harness.models import (
    GuardrailDecision,
    GuardrailStage,
    HarnessRunConfig,
    HarnessSession,
    HarnessSessionStatus,
    HarnessTerminationReason,
    ReplayMode,
)
from servicepilot.harness.runtime import (
    AgentRuntimeHarness,
    UnsupportedResumeError,
)


class BlockingGuardrail:
    name = "blocking_test_guardrail"

    def evaluate(
        self, stage: GuardrailStage, payload: dict[str, object]
    ) -> GuardrailDecision:
        return GuardrailDecision(
            allowed=stage is not GuardrailStage.INPUT,
            guardrail=self.name,
            reason="blocked in test",
        )


def config_for(scenario_id: str) -> HarnessRunConfig:
    return HarnessRunConfig(
        code_revision="test",
        scenario_sha256=hashlib.sha256(scenario_id.encode()).hexdigest(),
    )


@pytest.mark.asyncio
async def test_replay_is_verify_only_and_does_not_mutate_repository() -> None:
    scenario = next(
        item
        for item in build_phase3_scenarios()
        if item.intent is Intent.CANCEL_ORDER and item.accept_confirmation
    )
    trajectory, result, repository = await EvaluationHarness().run_scenario(
        scenario
    )
    audits_before = repository.list_audit_events()

    session = AgentRuntimeHarness().replay(
        trajectory=trajectory,
        scenario=scenario,
        config=config_for(scenario.scenario_id),
        mode=ReplayMode.VERIFY_ONLY,
    )

    assert result.task_success is True
    assert session.status is HarnessSessionStatus.REPLAYED
    assert session.termination_reason is HarnessTerminationReason.REPLAY_COMPLETED
    assert repository.list_audit_events() == audits_before


@pytest.mark.asyncio
async def test_completed_checkpoint_resume_returns_without_rerunning_agent() -> None:
    scenario = build_phase3_scenarios()[0]
    trajectory, _, _ = await EvaluationHarness().run_scenario(scenario)
    config = config_for(scenario.scenario_id)
    store = InMemoryCheckpointStore()
    runtime = AgentRuntimeHarness(checkpoint_store=store)
    session_id = runtime.session_id(scenario, config)
    completed = HarnessSession(
        session_id=session_id,
        scenario_id=scenario.scenario_id,
        config=config,
        status=HarnessSessionStatus.COMPLETED,
        termination_reason=HarnessTerminationReason.COMPLETED,
        trajectory=trajectory,
    )
    store.save(completed)

    resumed = await runtime.run(
        scenario=scenario,
        agent=RuleBasedSingleAgent(),
        simulator=FSMUserSimulator(scenario),
        gateway=None,  # type: ignore[arg-type]
        config=config,
        resume=True,
    )

    assert resumed == completed


@pytest.mark.asyncio
async def test_running_checkpoint_resume_is_explicitly_unsupported() -> None:
    scenario = build_phase3_scenarios()[0]
    config = config_for(scenario.scenario_id)
    store = InMemoryCheckpointStore()
    runtime = AgentRuntimeHarness(checkpoint_store=store)
    store.save(
        HarnessSession(
            session_id=runtime.session_id(scenario, config),
            scenario_id=scenario.scenario_id,
            config=config,
            status=HarnessSessionStatus.RUNNING,
        )
    )

    with pytest.raises(UnsupportedResumeError):
        await runtime.run(
            scenario=scenario,
            agent=RuleBasedSingleAgent(),
            simulator=FSMUserSimulator(scenario),
            gateway=None,  # type: ignore[arg-type]
            config=config,
            resume=True,
        )


@pytest.mark.asyncio
async def test_input_guardrail_stops_before_agent_or_tools() -> None:
    scenario = build_phase3_scenarios()[0]
    runtime = AgentRuntimeHarness(
        guardrails=GuardrailPipeline((BlockingGuardrail(),))
    )

    session = await runtime.run(
        scenario=scenario,
        agent=RuleBasedSingleAgent(),
        simulator=FSMUserSimulator(scenario),
        gateway=None,  # type: ignore[arg-type]
        config=config_for(scenario.scenario_id),
    )

    assert session.status is HarnessSessionStatus.FAILED
    assert session.termination_reason is HarnessTerminationReason.GUARDRAIL_STOP
    assert session.trajectory is None

