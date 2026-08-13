"""Thread-safe in-memory repository implementing authoritative test storage."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from threading import RLock
from typing import Any, Protocol

from servicepilot.domain.errors import NotFoundError
from servicepilot.domain.models import (
    AuditEvent,
    Coupon,
    Delivery,
    DeliveryIssue,
    HandoffTicket,
    Merchant,
    Order,
    PaymentRecord,
    Refund,
    SyntheticDataset,
)


class DomainRepository(Protocol):
    """Storage contract consumed by transaction services."""

    def transaction(self) -> AbstractContextManager[None]: ...
    def add_order(self, order: Order) -> None: ...
    def get_order(self, order_id: str) -> Order: ...
    def list_orders(self, user_id: str) -> tuple[Order, ...]: ...
    def save_order(self, order: Order) -> None: ...
    def add_coupon(self, coupon: Coupon) -> None: ...
    def get_coupon(self, coupon_id: str) -> Coupon: ...
    def save_coupon(self, coupon: Coupon) -> None: ...
    def add_refund(self, refund: Refund) -> None: ...
    def list_refunds(self, order_id: str) -> tuple[Refund, ...]: ...
    def get_refund(self, refund_id: str) -> Refund: ...
    def add_payment(self, payment: PaymentRecord) -> None: ...
    def list_payments(self, order_id: str) -> tuple[PaymentRecord, ...]: ...
    def add_merchant(self, merchant: Merchant) -> None: ...
    def get_merchant(self, merchant_id: str) -> Merchant: ...
    def add_delivery(self, delivery: Delivery) -> None: ...
    def get_delivery(self, order_id: str) -> Delivery: ...
    def save_delivery(self, delivery: Delivery) -> None: ...
    def add_delivery_issue(self, issue: DeliveryIssue) -> None: ...
    def list_delivery_issues(self, order_id: str) -> tuple[DeliveryIssue, ...]: ...
    def add_handoff_ticket(self, ticket: HandoffTicket) -> None: ...
    def list_handoff_tickets(self, order_id: str) -> tuple[HandoffTicket, ...]: ...
    def add_audit_event(self, event: AuditEvent) -> None: ...
    def list_audit_events(self) -> tuple[AuditEvent, ...]: ...
    def get_idempotent_result(self, action: str, key: str) -> tuple[str, Any] | None: ...
    def save_idempotent_result(
        self, action: str, key: str, fingerprint: str, result: Any
    ) -> None: ...


class InMemoryRepository:
    """Repository with a re-entrant transaction boundary for atomic services."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._orders: dict[str, Order] = {}
        self._coupons: dict[str, Coupon] = {}
        self._refunds: dict[str, Refund] = {}
        self._payments: dict[str, PaymentRecord] = {}
        self._merchants: dict[str, Merchant] = {}
        self._deliveries: dict[str, Delivery] = {}
        self._delivery_issues: dict[str, DeliveryIssue] = {}
        self._handoff_tickets: dict[str, HandoffTicket] = {}
        self._audits: list[AuditEvent] = []
        self._idempotency: dict[tuple[str, str], tuple[str, Any]] = {}

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            yield

    def add_order(self, order: Order) -> None:
        with self._lock:
            self._orders[order.order_id] = order

    def get_order(self, order_id: str) -> Order:
        with self._lock:
            try:
                return self._orders[order_id]
            except KeyError as exc:
                raise NotFoundError(f"order not found: {order_id}") from exc

    def list_orders(self, user_id: str) -> tuple[Order, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (order for order in self._orders.values() if order.user_id == user_id),
                    key=lambda order: order.created_at,
                    reverse=True,
                )
            )

    def save_order(self, order: Order) -> None:
        with self._lock:
            self._orders[order.order_id] = order

    def add_coupon(self, coupon: Coupon) -> None:
        with self._lock:
            self._coupons[coupon.coupon_id] = coupon

    def get_coupon(self, coupon_id: str) -> Coupon:
        with self._lock:
            try:
                return self._coupons[coupon_id]
            except KeyError as exc:
                raise NotFoundError(f"coupon not found: {coupon_id}") from exc

    def save_coupon(self, coupon: Coupon) -> None:
        with self._lock:
            self._coupons[coupon.coupon_id] = coupon

    def add_refund(self, refund: Refund) -> None:
        with self._lock:
            self._refunds[refund.refund_id] = refund

    def list_refunds(self, order_id: str) -> tuple[Refund, ...]:
        with self._lock:
            return tuple(refund for refund in self._refunds.values() if refund.order_id == order_id)

    def get_refund(self, refund_id: str) -> Refund:
        with self._lock:
            try:
                return self._refunds[refund_id]
            except KeyError as exc:
                raise NotFoundError(f"refund not found: {refund_id}") from exc

    def add_payment(self, payment: PaymentRecord) -> None:
        with self._lock:
            self._payments[payment.payment_id] = payment

    def list_payments(self, order_id: str) -> tuple[PaymentRecord, ...]:
        with self._lock:
            return tuple(
                payment for payment in self._payments.values() if payment.order_id == order_id
            )

    def add_merchant(self, merchant: Merchant) -> None:
        with self._lock:
            self._merchants[merchant.merchant_id] = merchant

    def get_merchant(self, merchant_id: str) -> Merchant:
        with self._lock:
            try:
                return self._merchants[merchant_id]
            except KeyError as exc:
                raise NotFoundError(f"merchant not found: {merchant_id}") from exc

    def add_delivery(self, delivery: Delivery) -> None:
        with self._lock:
            self._deliveries[delivery.order_id] = delivery

    def get_delivery(self, order_id: str) -> Delivery:
        with self._lock:
            try:
                return self._deliveries[order_id]
            except KeyError as exc:
                raise NotFoundError(f"delivery not found: {order_id}") from exc

    def save_delivery(self, delivery: Delivery) -> None:
        with self._lock:
            self._deliveries[delivery.order_id] = delivery

    def add_delivery_issue(self, issue: DeliveryIssue) -> None:
        with self._lock:
            self._delivery_issues[issue.issue_id] = issue

    def list_delivery_issues(self, order_id: str) -> tuple[DeliveryIssue, ...]:
        with self._lock:
            return tuple(
                issue for issue in self._delivery_issues.values() if issue.order_id == order_id
            )

    def add_handoff_ticket(self, ticket: HandoffTicket) -> None:
        with self._lock:
            self._handoff_tickets[ticket.ticket_id] = ticket

    def list_handoff_tickets(self, order_id: str) -> tuple[HandoffTicket, ...]:
        with self._lock:
            return tuple(
                ticket for ticket in self._handoff_tickets.values() if ticket.order_id == order_id
            )

    def load_dataset(self, dataset: SyntheticDataset) -> None:
        with self._lock:
            for order in dataset.orders:
                self._orders[order.order_id] = order
            for payment in dataset.payments:
                self._payments[payment.payment_id] = payment
            for coupon in dataset.coupons:
                self._coupons[coupon.coupon_id] = coupon
            for merchant in dataset.merchants:
                self._merchants[merchant.merchant_id] = merchant
            for delivery in dataset.deliveries:
                self._deliveries[delivery.order_id] = delivery

    def add_audit_event(self, event: AuditEvent) -> None:
        with self._lock:
            self._audits.append(event)

    def list_audit_events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._audits)

    def get_idempotent_result(self, action: str, key: str) -> tuple[str, Any] | None:
        with self._lock:
            return self._idempotency.get((action, key))

    def save_idempotent_result(self, action: str, key: str, fingerprint: str, result: Any) -> None:
        with self._lock:
            self._idempotency[(action, key)] = (fingerprint, result)
