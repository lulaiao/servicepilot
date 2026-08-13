import pytest

from servicepilot.routing.action_evidence import (
    bind_evidence_backed_actions,
    extract_requested_action_evidence,
    extract_requested_actions,
)
from servicepilot.routing.factored_intent import FactoredIntentResult, IssueType, RequestedAction
from servicepilot.routing.models import RiskLevel
from servicepilot.training.factored_classifier_catalog import build_factored_classifier_sft


def test_deterministic_actions_match_every_factored_catalog_target() -> None:
    for record in build_factored_classifier_sft():
        text = record.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1]
        target = FactoredIntentResult.model_validate_json(record.messages[1]["content"])

        assert set(extract_requested_actions(text)) == set(target.requested_actions), (
            record.source_record_id
        )


@pytest.mark.parametrize(
    "text",
    [
        "订单存在重复收费，但暂不退款",
        "只核实错发问题，不要取消订单",
        "配送延迟，先不投诉",
        "我还没决定是否退款",
    ],
)
def test_negated_or_undecided_actions_are_not_emitted(text: str) -> None:
    assert extract_requested_actions(text) == ()


def test_full_refund_dominates_generic_refund_match() -> None:
    assert extract_requested_actions("请办理整单全额退款58元") == (RequestedAction.FULL_REFUND,)


def test_action_evidence_contains_auditable_source_span() -> None:
    text = "订单继续有效，请重新预约送达时间"
    evidence = extract_requested_action_evidence(text)

    assert len(evidence) == 1
    assert evidence[0].action is RequestedAction.RESCHEDULE
    assert text[evidence[0].start : evidence[0].end] == evidence[0].text


def test_binding_removes_hallucination_and_recovers_explicit_action() -> None:
    generated = FactoredIntentResult(
        issue_type=IssueType.DUPLICATE_CHARGE,
        requested_actions=(RequestedAction.CANCEL_ORDER,),
        risk_level=RiskLevel.HIGH,
        confidence=0.9,
        needs_clarification=False,
    )

    no_action = bind_evidence_backed_actions(generated, "同一交易发生重复扣款")
    explicit = bind_evidence_backed_actions(generated, "重复扣款，请退款12元")

    assert no_action.requested_actions == ()
    assert explicit.requested_actions == (RequestedAction.PARTIAL_REFUND,)
