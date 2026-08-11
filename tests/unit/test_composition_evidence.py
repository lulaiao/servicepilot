from servicepilot.eval.models import Intent
from servicepilot.routing.composition_evidence import (
    bind_composition_evidence,
    extract_composition_evidence,
)
from servicepilot.routing.models import IntentResult, RiskLevel


def result(primary: Intent, secondary: tuple[Intent, ...] = ()) -> IntentResult:
    return IntentResult(
        primary_intent=primary,
        secondary_intents=secondary,
        slots={"order_id": None, "reason": None, "requested_amount": None},
        risk_level=RiskLevel.MEDIUM,
        confidence=0.9,
        needs_clarification=True,
    )


def test_binds_missing_secondary_when_both_requests_are_explicit() -> None:
    value = bind_composition_evidence(
        result(Intent.DELIVERY_DELAY), "履约已经逾期，还需要人工投诉处理"
    )

    assert value.primary_intent is Intent.DELIVERY_DELAY
    assert value.secondary_intents == (Intent.COMPLAINT_ESCALATION,)


def test_normalizes_reversed_composition_order() -> None:
    value = bind_composition_evidence(
        result(Intent.COMPLAINT_ESCALATION), "请人工介入，同时处理配送超时"
    )

    assert value.primary_intent is Intent.DELIVERY_DELAY
    assert value.secondary_intents == (Intent.COMPLAINT_ESCALATION,)


def test_does_not_bind_negated_escalation() -> None:
    text = "只登记运输延误，不创建人工工单"

    assert extract_composition_evidence(text) is None
    assert bind_composition_evidence(result(Intent.DELIVERY_DELAY), text) == result(
        Intent.DELIVERY_DELAY
    )


def test_does_not_bind_from_single_domain_or_unrelated_model_output() -> None:
    assert extract_composition_evidence("请创建人工投诉工单") is None
    value = result(Intent.OUT_OF_SCOPE)
    assert bind_composition_evidence(
        value, "配送已经超时，还需要人工投诉处理"
    ) == value
