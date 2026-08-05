"""Thread-safe in-memory repository implementing authoritative test storage."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from threading import RLock
from typing import Any, Protocol

from servicepilot.domain.errors import NotFoundError
from servicepilot.domain.models import AuditEvent, Coupon, Order, Refund


class DomainRepository(Protocol):
    """Storage contract consumed by transaction services."""

    def transaction(self) -> AbstractContextManager[None]: ...
    def add_order(self, order: Order) -> None: ...
    def get_order(self, order_id: str) -> Order: ...
    def save_order(self, order: Order) -> None: ...
    def add_coupon(self, coupon: Coupon) -> None: ...
    def get_coupon(self, coupon_id: str) -> Coupon: ...
    def save_coupon(self, coupon: Coupon) -> None: ...
    def add_refund(self, refund: Refund) -> None: ...
    def list_refunds(self, order_id: str) -> tuple[Refund, ...]: ...
    def add_audit_event(self, event: AuditEvent) -> None: ...
    def list_audit_events(self) -> tuple[AuditEvent, ...]: ...
    def get_idempotent_result(
        self, action: str, key: str
    ) -> tuple[str, Any] | None: ...
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
            return tuple(
                refund
                for refund in self._refunds.values()
                if refund.order_id == order_id
            )

    def add_audit_event(self, event: AuditEvent) -> None:
        with self._lock:
            self._audits.append(event)

    def list_audit_events(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._audits)

    def get_idempotent_result(
        self, action: str, key: str
    ) -> tuple[str, Any] | None:
        with self._lock:
            return self._idempotency.get((action, key))

    def save_idempotent_result(
        self, action: str, key: str, fingerprint: str, result: Any
    ) -> None:
        with self._lock:
            self._idempotency[(action, key)] = (fingerprint, result)
