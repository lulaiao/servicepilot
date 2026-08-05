"""Explicit order state transitions."""

from dataclasses import replace
from typing import Final

from servicepilot.domain.errors import InvalidTransitionError
from servicepilot.domain.models import Order, OrderStatus

ALLOWED_ORDER_TRANSITIONS: Final[dict[OrderStatus, frozenset[OrderStatus]]] = {
    OrderStatus.CREATED: frozenset({OrderStatus.PAID, OrderStatus.CANCELLED}),
    OrderStatus.PAID: frozenset({OrderStatus.ACCEPTED, OrderStatus.CANCELLED}),
    OrderStatus.ACCEPTED: frozenset({OrderStatus.PREPARING, OrderStatus.CANCELLED}),
    OrderStatus.PREPARING: frozenset({OrderStatus.PICKED_UP}),
    OrderStatus.PICKED_UP: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


def transition_order(order: Order, target: OrderStatus) -> Order:
    """Return a version-incremented order after validating the transition."""
    if target not in ALLOWED_ORDER_TRANSITIONS[order.status]:
        raise InvalidTransitionError(
            f"order {order.order_id} cannot transition from {order.status} to {target}"
        )
    return replace(order, status=target, version=order.version + 1)

