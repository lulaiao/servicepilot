"""Strongly typed authoritative records for the synthetic business simulator."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class OrderStatus(StrEnum):
    CREATED = "CREATED"
    PAID = "PAID"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class RefundStatus(StrEnum):
    NONE = "NONE"
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class PaymentStatus(StrEnum):
    CAPTURED = "CAPTURED"
    REVERSED = "REVERSED"


class CouponStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    USED = "USED"
    RESTORED = "RESTORED"
    EXPIRED = "EXPIRED"


class MerchantStatus(StrEnum):
    OPEN = "OPEN"
    BUSY = "BUSY"
    CLOSED = "CLOSED"


class DeliveryStatus(StrEnum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    PICKED_UP = "PICKED_UP"
    DELIVERED = "DELIVERED"
    DELAYED = "DELAYED"


class BusinessType(StrEnum):
    FOOD_DELIVERY = "FOOD_DELIVERY"
    LOCAL_SERVICE = "LOCAL_SERVICE"


@dataclass(frozen=True)
class Order:
    order_id: str
    user_id: str
    merchant_id: str
    status: OrderStatus
    paid_amount: Decimal
    coupon_id: str | None
    city: str
    business_type: BusinessType
    created_at: datetime
    policy_version: str
    version: int = 1
    non_refundable: bool = False

    def __post_init__(self) -> None:
        if self.paid_amount <= 0:
            raise ValueError("paid_amount must be positive")
        if self.version < 1:
            raise ValueError("version must be positive")


@dataclass(frozen=True)
class PaymentRecord:
    payment_id: str
    order_id: str
    amount: Decimal
    status: PaymentStatus
    charged_at: datetime
    duplicate_of: str | None = None


@dataclass(frozen=True)
class Refund:
    refund_id: str
    order_id: str
    amount: Decimal
    reason: str
    status: RefundStatus
    policy_version: str
    evidence_ids: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True)
class Coupon:
    coupon_id: str
    user_id: str
    status: CouponStatus
    order_id: str | None
    version: int = 1


@dataclass(frozen=True)
class Merchant:
    merchant_id: str
    status: MerchantStatus
    city: str
    version: int = 1


@dataclass(frozen=True)
class Delivery:
    order_id: str
    status: DeliveryStatus
    scheduled_at: datetime
    version: int = 1


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str
    policy_version: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    trace_id: str
    action: str
    target_id: str
    outcome: str
    idempotency_key: str | None
    entity_version: int | None
    occurred_at: datetime
    detail: str


@dataclass(frozen=True)
class WritePreview:
    action: str
    target_id: str
    confirmation_token: str
    expected_version: int
    policy_version: str
    evidence_ids: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class SyntheticDataset:
    orders: tuple[Order, ...]
    payments: tuple[PaymentRecord, ...]
    coupons: tuple[Coupon, ...]
    merchants: tuple[Merchant, ...]
    deliveries: tuple[Delivery, ...]
