import pytest

from servicepilot.eval.hard_catalog import ScenarioGoldAgent, build_hard_eval_v2
from servicepilot.eval.models import Intent
from servicepilot.harness.evaluation import EvaluationHarness


def test_hard_catalog_has_twenty_combinations_per_intent() -> None:
    cases = build_hard_eval_v2()
    assert len(cases) == len(Intent) * 20
    assert len({item.case_id for item in cases}) == len(cases)
    assert len({item.semantic_signature_sha256 for item in cases}) == len(cases)
    for intent in Intent:
        assert sum(item.scenario.intent is intent for item in cases) == 20


@pytest.mark.asyncio
async def test_hard_catalog_is_executable_by_authoritative_rule_agent() -> None:
    harness = EvaluationHarness()
    failures = []
    for case in build_hard_eval_v2():
        agent = ScenarioGoldAgent(case.scenario)
        _, judge, _ = await harness.run_scenario(case.scenario, agent=agent)
        if not judge.task_success:
            failures.append((case.case_id, judge.failure_reasons))
    assert failures == []
