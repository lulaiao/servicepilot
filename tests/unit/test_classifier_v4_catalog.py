from collections import Counter

import pytest

from servicepilot.eval.hard_catalog import ScenarioGoldAgent
from servicepilot.eval.models import Intent
from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.training.classifier_v4_catalog import (
    build_classifier_v4_dev_scenarios,
    build_classifier_v4_sft,
    build_classifier_v4_utterances,
)
from servicepilot.training.data_models import DataSplit


def _shingles(text: str, size: int = 5) -> set[str]:
    value = "".join(text.lower().split())
    return {value[index : index + size] for index in range(max(1, len(value) - size + 1))}


def test_v4_catalog_is_balanced_and_has_no_sealed_examples() -> None:
    utterances = build_classifier_v4_utterances()
    counts = Counter((item.split, item.intent) for item in utterances)

    assert len(utterances) == 108
    assert all(counts[(DataSplit.TRAIN, intent)] == 6 for intent in Intent)
    assert all(counts[(DataSplit.DEV, intent)] == 3 for intent in Intent)
    assert all(item.split is not DataSplit.SEALED_TEST for item in utterances)
    assert len({item.text for item in utterances}) == len(utterances)


def test_v4_catalog_has_no_cross_split_near_duplicates() -> None:
    utterances = build_classifier_v4_utterances()
    train = [item for item in utterances if item.split is DataSplit.TRAIN]
    dev = [item for item in utterances if item.split is DataSplit.DEV]
    pairs = []
    for left in train:
        left_shingles = _shingles(left.text)
        for right in dev:
            right_shingles = _shingles(right.text)
            score = len(left_shingles & right_shingles) / len(left_shingles | right_shingles)
            if score >= 0.8:
                pairs.append((left.utterance_id, right.utterance_id, score))
    assert pairs == []


def test_v4_sft_uses_executable_multi_intent_tuple() -> None:
    records = build_classifier_v4_sft()
    multi = [item for item in records if "multi_intent" in item.source_record_id]

    assert len(records) == 108
    assert len({item.record_id for item in records}) == len(records)
    assert all(
        '"primary_intent": "delivery_delay"' in item.messages[1]["content"] for item in multi
    )
    assert all('"complaint_escalation"' in item.messages[1]["content"] for item in multi)


def test_v4_dev_scenarios_are_dev_only_and_balanced() -> None:
    scenarios = build_classifier_v4_dev_scenarios()

    assert len(scenarios) == 36
    assert all(item.scenario_id.startswith("exec-v4-dev-") for item in scenarios)
    assert all(sum(item.intent is intent for item in scenarios) == 3 for intent in Intent)


@pytest.mark.asyncio
async def test_v4_dev_scenarios_have_executable_gold_workflows() -> None:
    failures = []
    harness = EvaluationHarness()
    for scenario in build_classifier_v4_dev_scenarios():
        _, judge, _ = await harness.run_scenario(scenario, agent=ScenarioGoldAgent(scenario))
        if not judge.task_success:
            failures.append((scenario.scenario_id, judge.failure_reasons))
    assert failures == []
