import asyncio
import hashlib

import pytest

from servicepilot.agents.rule_baseline import RuleBasedSingleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.models import Intent
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.harness.checkpoints import InMemoryCheckpointStore
from servicepilot.harness.evaluation import (
    EvaluationHarness,
    build_trial_environment,
)
from servicepilot.harness.guardrails import GuardrailPipeline
from servicepilot.harness.models import (
    GuardrailDecision,
    GuardrailStage,
    HarnessBudgets,
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
from servicepilot.mcp_gateway.faults import FaultKind


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


class ToolBlockingGuardrail:
    name = "tool_blocking_test_guardrail"

    def evaluate(
        self, stage: GuardrailStage, payload: dict[str, object]
    ) -> GuardrailDecision:
        blocked = (
            stage is GuardrailStage.TOOL
            and payload.get("tool_name") == "create_refund_request"
        )
        return GuardrailDecision(
            allowed=not blocked,
            guardrail=self.name,
            reason="blocked high-risk write" if blocked else "allowed",
        )


class TokenReportingAgent(RuleBasedSingleAgent):
    model_tokens_used = 2


class SlowAgent(RuleBasedSingleAgent):
    async def run(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        await asyncio.sleep(0.02)
        return await super().run(*args, **kwargs)  # type: ignore[arg-type]


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
async def test_resume_after_checkpointed_high_risk_write_does_not_repeat_refund() -> None:
    scenario = next(
        item
        for item in build_phase3_scenarios()
        if item.intent is Intent.PARTIAL_REFUND and not item.faults
    ).model_copy(
        update={
            "faults": {
                "create_refund_request": (FaultKind.LOST_RESPONSE,)
            }
        }
    )
    config = config_for(scenario.scenario_id)
    store = InMemoryCheckpointStore()
    runtime = AgentRuntimeHarness(checkpoint_store=store)
    environment = build_trial_environment(scenario, config.budgets)

    interrupted = await runtime.run(
        scenario=scenario,
        agent=RuleBasedSingleAgent(),
        simulator=FSMUserSimulator(scenario),
        gateway=environment.gateway,
        config=config,
        interrupt_after_committed_tool="create_refund_request",
    )

    assert interrupted.status is HarnessSessionStatus.INTERRUPTED
    assert interrupted.termination_reason is HarnessTerminationReason.INTERRUPTED
    assert len(environment.repository.list_refunds(scenario.order_id)) == 1
    audits_after_commit = environment.repository.list_audit_events()
    committed_writes = [
        step
        for step in interrupted.tool_steps
        if step.tool_name == "create_refund_request"
        and step.status.value == "committed"
    ]
    assert len(committed_writes) == 1
    assert committed_writes[0].result is not None
    assert committed_writes[0].result["attempts"] == 2

    resumed = await runtime.run(
        scenario=scenario,
        agent=RuleBasedSingleAgent(),
        simulator=FSMUserSimulator(scenario),
        gateway=environment.gateway,
        config=config,
        resume=True,
    )

    assert resumed.status is HarnessSessionStatus.COMPLETED
    assert resumed.trajectory is not None
    assert resumed.trajectory.claimed_success is True
    assert len(environment.repository.list_refunds(scenario.order_id)) == 1
    assert environment.repository.list_audit_events() == audits_after_commit
    assert any(event.kind == "session_resumed" for event in resumed.events)


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


@pytest.mark.asyncio
async def test_tool_guardrail_blocks_write_before_gateway() -> None:
    scenario = next(
        item
        for item in build_phase3_scenarios()
        if item.intent is Intent.PARTIAL_REFUND and not item.faults
    )
    config = config_for(scenario.scenario_id)
    environment = build_trial_environment(scenario, config.budgets)
    runtime = AgentRuntimeHarness(
        guardrails=GuardrailPipeline((ToolBlockingGuardrail(),))
    )

    session = await runtime.run(
        scenario=scenario,
        agent=RuleBasedSingleAgent(),
        simulator=FSMUserSimulator(scenario),
        gateway=environment.gateway,
        config=config,
    )

    assert session.termination_reason is HarnessTerminationReason.GUARDRAIL_STOP
    assert len(environment.repository.list_refunds(scenario.order_id)) == 0
    blocked = next(
        step for step in session.tool_steps if step.status.value == "blocked"
    )
    assert blocked.guardrail_decisions[0]["guardrail"] == ToolBlockingGuardrail.name


@pytest.mark.asyncio
async def test_tool_budget_has_explicit_termination() -> None:
    scenario = next(
        item
        for item in build_phase3_scenarios()
        if item.intent is Intent.CANCEL_ORDER and item.accept_confirmation
    )
    budgets = HarnessBudgets(max_tool_calls=1, timeout_seconds=0.1)
    config = config_for(scenario.scenario_id).model_copy(
        update={"budgets": budgets}
    )
    environment = build_trial_environment(scenario, budgets)

    session = await AgentRuntimeHarness().run(
        scenario=scenario,
        agent=RuleBasedSingleAgent(),
        simulator=FSMUserSimulator(scenario),
        gateway=environment.gateway,
        config=config,
    )

    assert session.termination_reason is HarnessTerminationReason.TOOL_BUDGET_EXHAUSTED
    assert session.tool_calls_used == 1


@pytest.mark.asyncio
async def test_retry_budget_has_explicit_termination() -> None:
    scenario = next(
        item
        for item in build_phase3_scenarios()
        if item.intent is Intent.ORDER_QUERY
    ).model_copy(
        update={"faults": {"get_order": (FaultKind.TIMEOUT,) * 3}}
    )
    budgets = HarnessBudgets(max_retries=2, timeout_seconds=0.1)
    config = config_for(scenario.scenario_id).model_copy(
        update={"budgets": budgets}
    )
    environment = build_trial_environment(scenario, budgets)

    session = await AgentRuntimeHarness().run(
        scenario=scenario,
        agent=RuleBasedSingleAgent(),
        simulator=FSMUserSimulator(scenario),
        gateway=environment.gateway,
        config=config,
    )

    assert session.termination_reason is HarnessTerminationReason.RETRY_BUDGET_EXHAUSTED
    assert session.retries_used == 2


@pytest.mark.asyncio
async def test_turn_and_token_budgets_have_explicit_termination() -> None:
    scenario = build_phase3_scenarios()[0]
    turn_budgets = HarnessBudgets(max_turns=1, timeout_seconds=0.1)
    turn_config = config_for(scenario.scenario_id).model_copy(
        update={"budgets": turn_budgets}
    )
    turn_environment = build_trial_environment(scenario, turn_budgets)
    turn_session = await AgentRuntimeHarness().run(
        scenario=scenario,
        agent=RuleBasedSingleAgent(),
        simulator=FSMUserSimulator(scenario),
        gateway=turn_environment.gateway,
        config=turn_config,
    )
    assert turn_session.termination_reason is HarnessTerminationReason.TURN_BUDGET_EXHAUSTED

    token_budgets = HarnessBudgets(
        max_model_tokens=1, timeout_seconds=0.1
    )
    token_config = config_for(scenario.scenario_id).model_copy(
        update={"budgets": token_budgets}
    )
    token_environment = build_trial_environment(scenario, token_budgets)
    token_session = await AgentRuntimeHarness().run(
        scenario=scenario,
        agent=TokenReportingAgent(),
        simulator=FSMUserSimulator(scenario),
        gateway=token_environment.gateway,
        config=token_config,
    )
    assert token_session.termination_reason is HarnessTerminationReason.TOKEN_BUDGET_EXHAUSTED
    assert token_session.model_tokens_used == 2


@pytest.mark.asyncio
async def test_time_budget_has_explicit_termination() -> None:
    scenario = build_phase3_scenarios()[0]
    budgets = HarnessBudgets(timeout_seconds=0.001)
    config = config_for(scenario.scenario_id).model_copy(
        update={"budgets": budgets}
    )
    environment = build_trial_environment(scenario, budgets)

    session = await AgentRuntimeHarness().run(
        scenario=scenario,
        agent=SlowAgent(),
        simulator=FSMUserSimulator(scenario),
        gateway=environment.gateway,
        config=config,
    )

    assert session.termination_reason is HarnessTerminationReason.TIME_BUDGET_EXHAUSTED
