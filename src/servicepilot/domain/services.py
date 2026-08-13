"""Preview-confirm-execute transaction services."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from json import dumps
from threading import RLock
from typing import Any, cast
from uuid import uuid4

from servicepilot.domain.errors import (
    ConfirmationError,
    IdempotencyConflictError,
    PolicyViolationError,
    VersionConflictError,
)
from servicepilot.domain.models import (
    AuditEvent,
    Coupon,
    CouponStatus,
    Delivery,
    Order,
    OrderStatus,
    Refund,
    RefundStatus,
    WritePreview,
)
from servicepilot.domain.repositories import DomainRepository
from servicepilot.domain.state_machine import transition_order
from servicepilot.policies.engine import PolicyEngine


@dataclass(frozen=True)
class _Confirmation:
    action: str
    target_id: str
    fingerprint: str


class TransactionService:
    """Only Phase 1 service authorized to perform authoritative writes."""

    def __init__(self, repository: DomainRepository, policy_engine: PolicyEngine) -> None:
        self.repository = repository
        self.policy_engine = policy_engine
        self._confirmations: dict[str, _Confirmation] = {}
        self._confirmation_lock = RLock()

    def preview_refund(self, order_id: str, reason: str, amount: Decimal) -> WritePreview:
        order = self.repository.get_order(order_id)
        decision = self.policy_engine.check_refund(order, reason, amount)
        if not decision.allowed:
            raise PolicyViolationError(decision.reason_code)
        payload = {
            "order_id": order_id,
            "reason": reason,
            "amount": str(amount),
        }
        return self._create_preview(
            "create_refund",
            order,
            payload,
            decision.policy_version,
            decision.evidence_ids,
            f"Request refund {amount} for {reason}",
        )

    def execute_refund(
        self,
        order_id: str,
        reason: str,
        amount: Decimal,
        confirmation_token: str,
        idempotency_key: str,
        expected_version: int,
    ) -> Refund:
        action = "create_refund"
        payload = {
            "order_id": order_id,
            "reason": reason,
            "amount": str(amount),
        }
        fingerprint = self._fingerprint(payload)
        with self.repository.transaction():
            previous = self._idempotent_result(action, idempotency_key, fingerprint)
            if previous is not None:
                return cast(Refund, previous)
            self._require_confirmation(
                confirmation_token, action, order_id, fingerprint, idempotency_key
            )
            order = self.repository.get_order(order_id)
            self._require_version(order, expected_version)
            decision = self.policy_engine.check_refund(order, reason, amount)
            if not decision.allowed:
                raise PolicyViolationError(decision.reason_code)
            already_requested = sum(
                (refund.amount for refund in self.repository.list_refunds(order_id)),
                Decimal("0"),
            )
            if already_requested + amount > order.paid_amount:
                raise PolicyViolationError("CUMULATIVE_AMOUNT_EXCEEDS_PAID")
            refund = Refund(
                refund_id=f"refund-{uuid4().hex}",
                order_id=order_id,
                amount=amount,
                reason=reason,
                status=RefundStatus.REQUESTED,
                policy_version=decision.policy_version,
                evidence_ids=decision.evidence_ids,
                created_at=self._now(),
            )
            self.repository.add_refund(refund)
            self.repository.save_order(replace(order, version=order.version + 1))
            self.repository.save_idempotent_result(action, idempotency_key, fingerprint, refund)
            self._consume_confirmation(confirmation_token)
            self._audit(action, order_id, "succeeded", idempotency_key, order.version + 1)
            return refund

    def preview_cancel(self, order_id: str) -> WritePreview:
        order = self.repository.get_order(order_id)
        decision = self.policy_engine.check_cancel(order)
        if not decision.allowed:
            raise PolicyViolationError(decision.reason_code)
        return self._create_preview(
            "cancel_order",
            order,
            {"order_id": order_id},
            decision.policy_version,
            decision.evidence_ids,
            f"Cancel order {order_id}",
        )

    def execute_cancel(
        self,
        order_id: str,
        confirmation_token: str,
        idempotency_key: str,
        expected_version: int,
    ) -> Order:
        action = "cancel_order"
        fingerprint = self._fingerprint({"order_id": order_id})
        with self.repository.transaction():
            previous = self._idempotent_result(action, idempotency_key, fingerprint)
            if previous is not None:
                return cast(Order, previous)
            self._require_confirmation(
                confirmation_token, action, order_id, fingerprint, idempotency_key
            )
            order = self.repository.get_order(order_id)
            self._require_version(order, expected_version)
            decision = self.policy_engine.check_cancel(order)
            if not decision.allowed:
                raise PolicyViolationError(decision.reason_code)
            updated = transition_order(order, OrderStatus.CANCELLED)
            self.repository.save_order(updated)
            self.repository.save_idempotent_result(action, idempotency_key, fingerprint, updated)
            self._consume_confirmation(confirmation_token)
            self._audit(action, order_id, "succeeded", idempotency_key, updated.version)
            return updated

    def preview_coupon_restore(self, order_id: str) -> WritePreview:
        order = self.repository.get_order(order_id)
        decision = self.policy_engine.check_coupon_restore(order)
        if not decision.allowed:
            raise PolicyViolationError(decision.reason_code)
        return self._create_preview(
            "restore_coupon",
            order,
            {"order_id": order_id, "coupon_id": order.coupon_id},
            decision.policy_version,
            decision.evidence_ids,
            f"Restore coupon {order.coupon_id}",
        )

    def preview_reschedule(self, order_id: str, new_time: datetime) -> WritePreview:
        if new_time.tzinfo is None:
            raise PolicyViolationError("NEW_TIME_MUST_HAVE_TIMEZONE")
        order = self.repository.get_order(order_id)
        decision = self.policy_engine.check_reschedule(order)
        if not decision.allowed:
            raise PolicyViolationError(decision.reason_code)
        return self._create_preview(
            "reschedule_order",
            order,
            {"order_id": order_id, "new_time": new_time.isoformat()},
            decision.policy_version,
            decision.evidence_ids,
            f"Reschedule order {order_id} to {new_time.isoformat()}",
        )

    def execute_reschedule(
        self,
        order_id: str,
        new_time: datetime,
        confirmation_token: str,
        idempotency_key: str,
        expected_version: int,
    ) -> Delivery:
        action = "reschedule_order"
        payload = {"order_id": order_id, "new_time": new_time.isoformat()}
        fingerprint = self._fingerprint(payload)
        with self.repository.transaction():
            previous = self._idempotent_result(action, idempotency_key, fingerprint)
            if previous is not None:
                return cast(Delivery, previous)
            self._require_confirmation(
                confirmation_token, action, order_id, fingerprint, idempotency_key
            )
            order = self.repository.get_order(order_id)
            self._require_version(order, expected_version)
            decision = self.policy_engine.check_reschedule(order)
            if not decision.allowed:
                raise PolicyViolationError(decision.reason_code)
            delivery = self.repository.get_delivery(order_id)
            updated = replace(
                delivery,
                scheduled_at=new_time,
                version=delivery.version + 1,
            )
            self.repository.save_delivery(updated)
            self.repository.save_order(replace(order, version=order.version + 1))
            self.repository.save_idempotent_result(action, idempotency_key, fingerprint, updated)
            self._consume_confirmation(confirmation_token)
            self._audit(action, order_id, "succeeded", idempotency_key, order.version + 1)
            return updated

    def execute_coupon_restore(
        self,
        order_id: str,
        confirmation_token: str,
        idempotency_key: str,
        expected_order_version: int,
    ) -> Coupon:
        action = "restore_coupon"
        with self.repository.transaction():
            order = self.repository.get_order(order_id)
            payload = {"order_id": order_id, "coupon_id": order.coupon_id}
            fingerprint = self._fingerprint(payload)
            previous = self._idempotent_result(action, idempotency_key, fingerprint)
            if previous is not None:
                return cast(Coupon, previous)
            self._require_confirmation(
                confirmation_token, action, order_id, fingerprint, idempotency_key
            )
            self._require_version(order, expected_order_version)
            decision = self.policy_engine.check_coupon_restore(order)
            if not decision.allowed:
                raise PolicyViolationError(decision.reason_code)
            if order.coupon_id is None:
                raise PolicyViolationError("ORDER_HAS_NO_COUPON")
            coupon = self.repository.get_coupon(order.coupon_id)
            restored = replace(
                coupon,
                status=CouponStatus.AVAILABLE,
                order_id=None,
                version=coupon.version + 1,
            )
            self.repository.save_coupon(restored)
            self.repository.save_order(replace(order, version=order.version + 1))
            self.repository.save_idempotent_result(action, idempotency_key, fingerprint, restored)
            self._consume_confirmation(confirmation_token)
            self._audit(action, order_id, "succeeded", idempotency_key, order.version + 1)
            return restored

    def _create_preview(
        self,
        action: str,
        order: Order,
        payload: Mapping[str, str | None],
        policy_version: str,
        evidence_ids: tuple[str, ...],
        summary: str,
    ) -> WritePreview:
        fingerprint = self._fingerprint(payload)
        token = uuid4().hex
        with self._confirmation_lock:
            self._confirmations[token] = _Confirmation(action, order.order_id, fingerprint)
        self._audit(action, order.order_id, "previewed", None, order.version)
        return WritePreview(
            action,
            order.order_id,
            token,
            order.version,
            policy_version,
            evidence_ids,
            summary,
        )

    def _require_confirmation(
        self,
        token: str,
        action: str,
        target_id: str,
        fingerprint: str,
        idempotency_key: str,
    ) -> None:
        with self._confirmation_lock:
            confirmation = self._confirmations.get(token)
        expected = _Confirmation(action, target_id, fingerprint)
        if confirmation != expected:
            self._audit(action, target_id, "rejected", idempotency_key, None, "confirmation")
            raise ConfirmationError("missing or mismatched confirmation token")

    def _consume_confirmation(self, token: str) -> None:
        with self._confirmation_lock:
            self._confirmations.pop(token, None)

    def _require_version(self, order: Order, expected_version: int) -> None:
        if order.version != expected_version:
            self._audit(
                "version_check",
                order.order_id,
                "rejected",
                None,
                order.version,
                f"expected={expected_version}",
            )
            raise VersionConflictError(
                f"expected version {expected_version}, found {order.version}"
            )

    def _idempotent_result(self, action: str, key: str, fingerprint: str) -> Any | None:
        previous = self.repository.get_idempotent_result(action, key)
        if previous is None:
            return None
        previous_fingerprint, result = previous
        if previous_fingerprint != fingerprint:
            raise IdempotencyConflictError(
                f"idempotency key {key!r} was used for a different request"
            )
        return result

    @staticmethod
    def _fingerprint(payload: Mapping[str, str | None]) -> str:
        serialized = dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(serialized.encode("utf-8")).hexdigest()

    def _audit(
        self,
        action: str,
        target_id: str,
        outcome: str,
        idempotency_key: str | None,
        entity_version: int | None,
        detail: str = "",
    ) -> None:
        self.repository.add_audit_event(
            AuditEvent(
                event_id=f"audit-{uuid4().hex}",
                trace_id=f"trace-{uuid4().hex}",
                action=action,
                target_id=target_id,
                outcome=outcome,
                idempotency_key=idempotency_key,
                entity_version=entity_version,
                occurred_at=self._now(),
                detail=detail,
            )
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
