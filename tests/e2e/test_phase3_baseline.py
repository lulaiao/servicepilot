import pytest

from servicepilot.domain.models import OrderStatus
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.judge import DeterministicJudge
from servicepilot.eval.models import ExpectedFinalState, Intent
from servicepilot.eval.runner import run_scenario, run_suite


def test_catalog_has_three_variants_for_every_intent() -> None:
    scenarios = build_phase3_scenarios()

    assert len(scenarios) == 36
    assert {scenario.intent for scenario in scenarios} == set(Intent)
    assert all(sum(item.intent is intent for item in scenarios) == 3 for intent in Intent)
    assert len({scenario.scenario_id for scenario in scenarios}) == 36


@pytest.mark.asyncio
async def test_confirmed_cancel_changes_authoritative_state() -> None:
    scenario = next(item for item in build_phase3_scenarios() if item.intent is Intent.CANCEL_ORDER)

    trajectory, result, repository = await run_scenario(scenario)

    assert result.task_success is True
    assert trajectory.claimed_success is True
    assert repository.get_order(scenario.order_id).status is OrderStatus.CANCELLED
    assert [event.tool_name for event in trajectory.events if event.tool_name] == [
        "preview_cancel",
        "cancel_order",
    ]


@pytest.mark.asyncio
async def test_fault_variant_recovers_without_extra_business_write() -> None:
    scenario = next(
        item
        for item in build_phase3_scenarios()
        if item.intent is Intent.PARTIAL_REFUND and item.faults
    )

    trajectory, result, repository = await run_scenario(scenario)

    assert result.task_success is True
    assert len(repository.list_refunds(scenario.order_id)) == 1
    preview_event = next(
        event for event in trajectory.events if event.tool_name == "preview_refund"
    )
    assert preview_event.result is not None
    assert preview_event.result["attempts"] == 2


@pytest.mark.asyncio
async def test_user_refusal_prevents_cancel_and_is_not_false_success() -> None:
    scenario = next(
        item
        for item in build_phase3_scenarios()
        if item.intent is Intent.CANCEL_ORDER and not item.accept_confirmation
    )

    trajectory, result, repository = await run_scenario(scenario)

    assert result.task_success is True
    assert result.false_success is False
    assert trajectory.claimed_success is False
    assert repository.get_order(scenario.order_id).status is OrderStatus.ACCEPTED
    assert all(event.tool_name != "cancel_order" for event in trajectory.events)


@pytest.mark.asyncio
async def test_false_success_is_detected_from_state_not_agent_claim() -> None:
    scenario = next(item for item in build_phase3_scenarios() if item.intent is Intent.ORDER_QUERY)
    trajectory, _, repository = await run_scenario(scenario)
    impossible_expectation = scenario.model_copy(
        update={
            "expected": ExpectedFinalState(
                order_status=OrderStatus.CANCELLED,
                write_expected=True,
            )
        }
    )

    result = DeterministicJudge().evaluate(impossible_expectation, trajectory, repository)

    assert trajectory.claimed_success is True
    assert result.final_state_correct is False
    assert result.false_success is True
    assert "FALSE_SUCCESS" in result.failure_reasons


@pytest.mark.asyncio
async def test_judge_rejects_called_tool_outside_allowed_contract() -> None:
    scenario = next(item for item in build_phase3_scenarios() if item.intent is Intent.ORDER_QUERY)
    trajectory, _, repository = await run_scenario(scenario)
    no_tool_contract = scenario.model_copy(update={"allowed_actions": (), "forbidden_actions": ()})

    result = DeterministicJudge().evaluate(no_tool_contract, trajectory, repository)

    assert "UNEXPECTED_ACTION" in result.failure_reasons
    assert result.tool_sequence_valid is False
    assert result.policy_compliant is False


@pytest.mark.asyncio
async def test_full_phase3_suite_is_executable() -> None:
    scenarios = build_phase3_scenarios()

    trajectories, results, report = await run_suite(scenarios)

    assert len(trajectories) == 36
    assert len(results) == 36
    assert report.scenario_count == 36
    assert report.executable_task_success_rate == 1.0
    assert report.final_state_accuracy == 1.0
    assert report.policy_violation_rate == 0.0
    assert report.false_success_rate == 0.0
