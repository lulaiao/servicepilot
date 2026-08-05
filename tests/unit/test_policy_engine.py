from dataclasses import replace
from decimal import Decimal

from servicepilot.domain.models import BusinessType, OrderStatus
from servicepilot.domain.synthetic import build_seed_order
from servicepilot.policies.engine import PolicyEngine


def test_partial_refund_decision_has_versioned_evidence() -> None:
    engine = PolicyEngine.default()
    order = replace(build_seed_order(), status=OrderStatus.DELIVERED)

    decision = engine.check_refund(order, "missing_item", Decimal("12.00"))

    assert decision.allowed is True
    assert decision.policy_version == "2026.1"
    assert decision.evidence_ids == ("policy_partial_refund_2026_1_section_3",)


def test_refund_amount_cannot_exceed_paid_amount() -> None:
    engine = PolicyEngine.default()
    order = replace(build_seed_order(), status=OrderStatus.DELIVERED)

    decision = engine.check_refund(order, "missing_item", Decimal("99.00"))

    assert decision.allowed is False
    assert decision.reason_code == "AMOUNT_EXCEEDS_PAID"


def test_policy_exception_rejects_non_refundable_booking() -> None:
    engine = PolicyEngine.default()
    order = replace(
        build_seed_order(),
        status=OrderStatus.DELIVERED,
        business_type=BusinessType.LOCAL_SERVICE,
        non_refundable=True,
    )

    decision = engine.check_refund(order, "changed_mind", Decimal("10.00"))

    assert decision.allowed is False
    assert decision.reason_code == "NON_REFUNDABLE_EXCEPTION"
    assert "policy_refund_exception_2026_1_section_8" in decision.evidence_ids


def test_engine_does_not_apply_wrong_policy_version() -> None:
    engine = PolicyEngine.default()
    order = replace(
        build_seed_order(),
        status=OrderStatus.DELIVERED,
        policy_version="2025.4",
    )

    decision = engine.check_refund(order, "missing_item", Decimal("12.00"))

    assert decision.allowed is False
    assert decision.reason_code == "POLICY_VERSION_UNAVAILABLE"
    assert decision.evidence_ids == ()
