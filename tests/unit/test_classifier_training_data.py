from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.models import Intent
from servicepilot.training import (
    DataSplit,
    build_failure_remediation_sft,
    classifier_target,
    visible_slots,
)
from servicepilot.training.expansion import (
    build_phase9_sealed_families,
    build_phase9_train_dev_families,
    build_phase9_train_dev_families_v2,
    expand_family_variants,
)


def test_visible_slots_never_copy_hidden_scenario_values() -> None:
    scenario = next(
        item for item in build_phase3_scenarios() if item.intent is Intent.PARTIAL_REFUND
    ).model_copy(update={"user_utterance": "这个商品有问题，我要申请部分退款"})
    target = classifier_target(scenario)
    assert target.slots["order_id"] is None
    assert target.slots["requested_amount"] is None
    assert target.needs_clarification


def test_visible_slots_extract_only_literal_values() -> None:
    assert visible_slots("订单号是 order-12345，退款 12.50 元") == {
        "order_id": "order-12345",
        "reason": None,
        "requested_amount": "12.50",
    }


def test_high_risk_intent_target_is_structured() -> None:
    scenario = next(item for item in build_phase3_scenarios() if item.intent is Intent.RESCHEDULE)
    target = classifier_target(scenario)
    assert target.primary_intent is Intent.RESCHEDULE
    assert target.risk_level.value == "high"
    assert target.confidence == 1.0


def test_multi_intent_target_matches_executable_agent_contract() -> None:
    scenario = next(item for item in build_phase3_scenarios() if item.intent is Intent.MULTI_INTENT)

    target = classifier_target(scenario)

    assert target.primary_intent is Intent.DELIVERY_DELAY
    assert target.secondary_intents == (Intent.COMPLAINT_ESCALATION,)


def test_failure_remediation_is_train_only_and_bounded() -> None:
    families = (
        build_phase9_sealed_families()
        + build_phase9_train_dev_families()
        + build_phase9_train_dev_families_v2()
    )
    variants = tuple(variant for family in families for variant in expand_family_variants(family))
    records = build_failure_remediation_sft(variants)
    assert len(records) == 60
    assert {item.split for item in records} == {DataSplit.TRAIN}
    assert len({item.record_id for item in records}) == len(records)
