import pytest

from servicepilot.agents import (
    RetrievalGatedTransactionalAgent,
    StaticPolicyEvidenceProvider,
)
from servicepilot.domain.models import OrderStatus
from servicepilot.eval import build_phase3_scenarios, run_scenario
from servicepilot.eval.models import Intent


def cancellation_scenario():
    return next(
        item
        for item in build_phase3_scenarios()
        if item.intent is Intent.CANCEL_ORDER and item.accept_confirmation
    )


@pytest.mark.asyncio
async def test_complete_retrieved_evidence_allows_transaction() -> None:
    scenario = cancellation_scenario()
    agent = RetrievalGatedTransactionalAgent(
        StaticPolicyEvidenceProvider({scenario.scenario_id: scenario.gold_evidence_ids})
    )

    trajectory, result, repository = await run_scenario(scenario, agent=agent)

    assert result.task_success is True
    assert repository.get_order(scenario.order_id).status is OrderStatus.CANCELLED
    assert any(event.tool_name == "search_policy" for event in trajectory.events)


@pytest.mark.asyncio
async def test_missing_retrieved_evidence_blocks_transaction_without_write() -> None:
    scenario = cancellation_scenario()
    agent = RetrievalGatedTransactionalAgent(StaticPolicyEvidenceProvider({}))

    trajectory, result, repository = await run_scenario(scenario, agent=agent)

    assert result.task_success is False
    assert "GOLD_EVIDENCE_MISSING" in result.failure_reasons
    assert repository.get_order(scenario.order_id).status is OrderStatus.ACCEPTED
    assert all(event.tool_name != "cancel_order" for event in trajectory.events)
