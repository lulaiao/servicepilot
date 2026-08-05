"""Versioned, executable policy assertions."""

from decimal import Decimal

from servicepilot.domain.models import (
    BusinessType,
    Order,
    OrderStatus,
    PolicyDecision,
)


class PolicyEngine:
    """Deterministic policy source used by writes and executable evaluation."""

    def __init__(self, version: str) -> None:
        self.version = version

    @classmethod
    def default(cls) -> "PolicyEngine":
        return cls(version="2026.1")

    def check_cancel(self, order: Order) -> PolicyDecision:
        version_error = self._check_version(order)
        if version_error is not None:
            return version_error
        evidence = ("policy_cancel_2026_1_section_2",)
        allowed = order.status in {
            OrderStatus.CREATED,
            OrderStatus.PAID,
            OrderStatus.ACCEPTED,
        }
        return PolicyDecision(
            allowed=allowed,
            reason_code="ELIGIBLE" if allowed else "ORDER_STATE_INELIGIBLE",
            policy_version=self.version,
            evidence_ids=evidence,
        )

    def check_refund(
        self, order: Order, reason: str, requested_amount: Decimal
    ) -> PolicyDecision:
        version_error = self._check_version(order)
        if version_error is not None:
            return version_error
        base_evidence = ("policy_partial_refund_2026_1_section_3",)
        if requested_amount <= 0:
            return PolicyDecision(
                False, "INVALID_AMOUNT", self.version, base_evidence
            )
        if requested_amount > order.paid_amount:
            return PolicyDecision(
                False, "AMOUNT_EXCEEDS_PAID", self.version, base_evidence
            )
        if order.status is not OrderStatus.DELIVERED:
            return PolicyDecision(
                False, "ORDER_STATE_INELIGIBLE", self.version, base_evidence
            )
        if (
            order.business_type is BusinessType.LOCAL_SERVICE
            and order.non_refundable
            and reason == "changed_mind"
        ):
            return PolicyDecision(
                False,
                "NON_REFUNDABLE_EXCEPTION",
                self.version,
                base_evidence
                + ("policy_refund_exception_2026_1_section_8",),
            )
        if reason not in {
            "missing_item",
            "wrong_item",
            "quality_issue",
            "duplicate_charge",
            "changed_mind",
        }:
            return PolicyDecision(
                False, "UNSUPPORTED_REASON", self.version, base_evidence
            )
        return PolicyDecision(True, "ELIGIBLE", self.version, base_evidence)

    def check_coupon_restore(self, order: Order) -> PolicyDecision:
        version_error = self._check_version(order)
        if version_error is not None:
            return version_error
        evidence = ("policy_coupon_restore_2026_1_section_5",)
        allowed = order.status is OrderStatus.CANCELLED and order.coupon_id is not None
        return PolicyDecision(
            allowed,
            "ELIGIBLE" if allowed else "COUPON_RESTORE_INELIGIBLE",
            self.version,
            evidence,
        )

    def _check_version(self, order: Order) -> PolicyDecision | None:
        if order.policy_version == self.version:
            return None
        return PolicyDecision(
            False,
            "POLICY_VERSION_UNAVAILABLE",
            self.version,
            (),
        )
