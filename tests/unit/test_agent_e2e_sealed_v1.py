import re
from collections import Counter

import pytest

from servicepilot.eval.agent_sealed_v1 import build_agent_e2e_sealed_v1
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.hard_catalog import ScenarioGoldAgent
from servicepilot.eval.models import Intent
from servicepilot.eval.runner import run_scenario
from servicepilot.training import build_classifier_v4_utterances


def normalized(text: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", text.lower())


def test_sealed_catalog_is_balanced_unique_and_post_selection() -> None:
    scenarios = build_agent_e2e_sealed_v1()

    assert len(scenarios) == 24
    assert len({item.scenario_id for item in scenarios}) == 24
    assert len({normalized(item.user_utterance) for item in scenarios}) == 24
    assert Counter(item.intent for item in scenarios) == Counter({intent: 2 for intent in Intent})


def test_sealed_text_has_no_exact_overlap_with_prior_baselines() -> None:
    reserved = {normalized(item.user_utterance) for item in build_phase3_scenarios()} | {
        normalized(item.text) for item in build_classifier_v4_utterances()
    }

    assert not reserved & {normalized(item.user_utterance) for item in build_agent_e2e_sealed_v1()}


def test_sealed_catalog_covers_safety_and_recovery_boundaries() -> None:
    scenarios = build_agent_e2e_sealed_v1()

    assert any(not item.accept_confirmation for item in scenarios)
    assert any(
        "LOST_RESPONSE" in {fault.value for faults in item.faults.values() for fault in faults}
        for item in scenarios
    )
    assert any(
        "TRANSIENT" in {fault.value for faults in item.faults.values() for fault in faults}
        for item in scenarios
    )
    injection = next(item for item in scenarios if "忽略确认" in item.user_utterance)
    assert injection.intent is Intent.OUT_OF_SCOPE
    assert not injection.allowed_actions
    assert injection.forbidden_actions


@pytest.mark.asyncio
async def test_gold_workflow_executes_all_sealed_fixtures() -> None:
    for scenario in build_agent_e2e_sealed_v1():
        _, result, _ = await run_scenario(scenario, agent=ScenarioGoldAgent(scenario))
        assert result.task_success, (scenario.scenario_id, result.failure_reasons)
