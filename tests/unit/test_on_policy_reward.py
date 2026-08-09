import pytest

from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.training.on_policy import (
    ExecutableClassifierReward,
    classifier_grpo_examples,
    gold_completion,
    model_owned_scenarios,
)


def test_grpo_examples_use_deployed_classifier_prompt() -> None:
    scenarios = build_phase3_scenarios()[:2]
    examples = classifier_grpo_examples(scenarios)
    assert len(examples) == 2
    assert examples[0]["scenario_id"] == scenarios[0].scenario_id
    assert "只输出一个JSON对象" in examples[0]["prompt"][0]["content"]


def test_deterministic_guardrail_owned_inputs_are_excluded() -> None:
    scenarios = build_phase3_scenarios()
    owned = model_owned_scenarios(scenarios)
    assert len(owned) < len(scenarios)
    assert not any(item.intent.value == "multi_intent" for item in owned)


@pytest.mark.asyncio
async def test_gold_classifier_completion_is_scored_by_executable_harness() -> None:
    scenario = build_phase3_scenarios()[0]
    adapter = ExecutableClassifierReward((scenario,))
    evidence = await adapter.score_async(gold_completion(scenario), scenario.scenario_id)
    assert evidence.parsed
    assert evidence.task_success
    assert evidence.reward.total > 0


@pytest.mark.asyncio
async def test_invalid_completion_fails_before_execution() -> None:
    scenario = build_phase3_scenarios()[0]
    adapter = ExecutableClassifierReward((scenario,))
    evidence = await adapter.score_async("任务已完成", scenario.scenario_id)
    assert not evidence.parsed
    assert evidence.reward.total == -1.0
    assert evidence.reward.hard_gate == "schema"


@pytest.mark.asyncio
async def test_guardrail_rescue_does_not_give_wrong_model_full_credit() -> None:
    scenarios = build_phase3_scenarios()
    high_risk = next(item for item in scenarios if item.intent.value == "cancel_order")
    wrong = next(item for item in scenarios if item.intent.value == "delivery_delay")
    adapter = ExecutableClassifierReward((high_risk,))
    evidence = await adapter.score_async(gold_completion(wrong), high_risk.scenario_id)
    assert evidence.guardrail_rescue
    assert evidence.reward.total < 0
    assert evidence.reward.hard_gate == "guardrail_rescue"


@pytest.mark.asyncio
async def test_benign_business_outcome_does_not_hide_classifier_mismatch() -> None:
    scenarios = build_phase3_scenarios()
    out_of_scope = next(item for item in scenarios if item.intent.value == "out_of_scope")
    order_query = next(item for item in scenarios if item.intent.value == "order_query")
    adapter = ExecutableClassifierReward((out_of_scope,))
    evidence = await adapter.score_async(
        gold_completion(order_query), out_of_scope.scenario_id
    )
    assert evidence.reward.total < 0
    assert evidence.reward.hard_gate == "classifier_contract_mismatch"


def test_trl_callable_accepts_conversational_completion_shape() -> None:
    scenario = build_phase3_scenarios()[0]
    adapter = ExecutableClassifierReward((scenario,))
    rewards = adapter(
        prompts=[[{"role": "user", "content": "prompt"}]],
        completions=[[{"role": "assistant", "content": gold_completion(scenario)}]],
        scenario_id=[scenario.scenario_id],
    )
    assert rewards[0] > 0
