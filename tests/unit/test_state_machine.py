from dataclasses import replace

import pytest

from servicepilot.domain.errors import InvalidTransitionError
from servicepilot.domain.models import OrderStatus
from servicepilot.domain.state_machine import transition_order
from servicepilot.domain.synthetic import build_seed_order


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.CREATED, OrderStatus.PAID),
        (OrderStatus.PAID, OrderStatus.ACCEPTED),
        (OrderStatus.ACCEPTED, OrderStatus.PREPARING),
        (OrderStatus.PREPARING, OrderStatus.PICKED_UP),
        (OrderStatus.PICKED_UP, OrderStatus.DELIVERED),
        (OrderStatus.CREATED, OrderStatus.CANCELLED),
        (OrderStatus.PAID, OrderStatus.CANCELLED),
        (OrderStatus.ACCEPTED, OrderStatus.CANCELLED),
    ],
)
def test_legal_order_transitions_increment_version(
    current: OrderStatus, target: OrderStatus
) -> None:
    order = replace(build_seed_order(), status=current, version=7)

    updated = transition_order(order, target)

    assert updated.status is target
    assert updated.version == 8


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (OrderStatus.DELIVERED, OrderStatus.CANCELLED),
        (OrderStatus.CANCELLED, OrderStatus.PAID),
        (OrderStatus.PICKED_UP, OrderStatus.PREPARING),
        (OrderStatus.PREPARING, OrderStatus.CANCELLED),
    ],
)
def test_illegal_order_transitions_are_rejected(
    current: OrderStatus, target: OrderStatus
) -> None:
    order = replace(build_seed_order(), status=current)

    with pytest.raises(InvalidTransitionError):
        transition_order(order, target)

