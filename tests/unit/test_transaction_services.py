from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal

import pytest

from servicepilot.domain.errors import (
    ConfirmationError,
    IdempotencyConflictError,
    PolicyViolationError,
    VersionConflictError,
)
from servicepilot.domain.models import CouponStatus, OrderStatus, RefundStatus
from servicepilot.domain.repositories import InMemoryRepository
from servicepilot.domain.services import TransactionService
from servicepilot.domain.synthetic import build_seed_coupon, build_seed_order
from servicepilot.policies.engine import PolicyEngine


def make_service(order_status: OrderStatus = OrderStatus.DELIVERED) -> TransactionService:
    repository = InMemoryRepository()
    repository.add_order(replace(build_seed_order(), status=order_status))
    repository.add_coupon(build_seed_coupon())
    return TransactionService(repository, PolicyEngine.default())


def test_refund_requires_preview_confirmation() -> None:
    service = make_service()

    with pytest.raises(ConfirmationError):
        service.execute_refund(
            order_id="ord-001",
            reason="missing_item",
            amount=Decimal("12.00"),
            confirmation_token="not-a-token",
            idempotency_key="refund-001",
            expected_version=1,
        )

    assert service.repository.list_refunds("ord-001") == ()
    assert service.repository.list_audit_events()[-1].outcome == "rejected"


def test_refund_is_idempotent_and_only_mutates_once() -> None:
    service = make_service()
    preview = service.preview_refund("ord-001", "missing_item", Decimal("12.00"))

    first = service.execute_refund(
        order_id="ord-001",
        reason="missing_item",
        amount=Decimal("12.00"),
        confirmation_token=preview.confirmation_token,
        idempotency_key="refund-001",
        expected_version=1,
    )
    second = service.execute_refund(
        order_id="ord-001",
        reason="missing_item",
        amount=Decimal("12.00"),
        confirmation_token=preview.confirmation_token,
        idempotency_key="refund-001",
        expected_version=1,
    )

    assert first == second
    assert first.status is RefundStatus.REQUESTED
    assert len(service.repository.list_refunds("ord-001")) == 1
    assert service.repository.get_order("ord-001").version == 2


def test_reusing_key_with_different_request_is_rejected() -> None:
    service = make_service()
    preview = service.preview_refund("ord-001", "missing_item", Decimal("12.00"))
    service.execute_refund(
        "ord-001",
        "missing_item",
        Decimal("12.00"),
        preview.confirmation_token,
        "refund-001",
        1,
    )

    with pytest.raises(IdempotencyConflictError):
        service.execute_refund(
            "ord-001",
            "missing_item",
            Decimal("10.00"),
            preview.confirmation_token,
            "refund-001",
            1,
        )


def test_stale_order_version_cannot_create_refund() -> None:
    service = make_service()
    preview = service.preview_refund("ord-001", "missing_item", Decimal("12.00"))

    with pytest.raises(VersionConflictError):
        service.execute_refund(
            "ord-001",
            "missing_item",
            Decimal("12.00"),
            preview.confirmation_token,
            "refund-001",
            99,
        )

    assert service.repository.list_refunds("ord-001") == ()


def test_policy_denial_cannot_be_bypassed() -> None:
    service = make_service()

    with pytest.raises(PolicyViolationError):
        service.preview_refund("ord-001", "missing_item", Decimal("1000.00"))


def test_cancel_and_coupon_restore_are_confirmed_and_idempotent() -> None:
    service = make_service(OrderStatus.ACCEPTED)
    cancel_preview = service.preview_cancel("ord-001")
    cancelled = service.execute_cancel(
        "ord-001",
        cancel_preview.confirmation_token,
        "cancel-001",
        1,
    )
    repeated = service.execute_cancel(
        "ord-001",
        cancel_preview.confirmation_token,
        "cancel-001",
        1,
    )

    assert cancelled == repeated
    assert cancelled.status is OrderStatus.CANCELLED
    assert cancelled.version == 2

    coupon_preview = service.preview_coupon_restore("ord-001")
    restored = service.execute_coupon_restore(
        "ord-001",
        coupon_preview.confirmation_token,
        "coupon-restore-001",
        expected_order_version=2,
    )
    restored_again = service.execute_coupon_restore(
        "ord-001",
        coupon_preview.confirmation_token,
        "coupon-restore-001",
        expected_order_version=2,
    )

    assert restored == restored_again
    assert restored.status is CouponStatus.AVAILABLE
    assert service.repository.get_order("ord-001").version == 3


def test_concurrent_duplicate_refund_creates_one_record() -> None:
    service = make_service()
    preview = service.preview_refund("ord-001", "missing_item", Decimal("12.00"))

    def execute() -> str:
        return service.execute_refund(
            "ord-001",
            "missing_item",
            Decimal("12.00"),
            preview.confirmation_token,
            "refund-concurrent-001",
            1,
        ).refund_id

    with ThreadPoolExecutor(max_workers=8) as executor:
        refund_ids = tuple(executor.map(lambda _: execute(), range(32)))

    assert len(set(refund_ids)) == 1
    assert len(service.repository.list_refunds("ord-001")) == 1


def test_confirmation_token_cannot_authorize_a_second_write() -> None:
    service = make_service()
    preview = service.preview_refund("ord-001", "missing_item", Decimal("12.00"))
    service.execute_refund(
        "ord-001",
        "missing_item",
        Decimal("12.00"),
        preview.confirmation_token,
        "refund-001",
        1,
    )

    with pytest.raises(ConfirmationError):
        service.execute_refund(
            "ord-001",
            "missing_item",
            Decimal("12.00"),
            preview.confirmation_token,
            "refund-002",
            2,
        )

    assert len(service.repository.list_refunds("ord-001")) == 1
