"""Seeded synthetic records for deterministic tests and scenarios."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from random import Random

from servicepilot.domain.models import (
    BusinessType,
    Coupon,
    CouponStatus,
    Delivery,
    DeliveryStatus,
    Merchant,
    MerchantStatus,
    Order,
    OrderStatus,
    PaymentRecord,
    PaymentStatus,
    SyntheticDataset,
)

BASE_TIME = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def build_seed_order() -> Order:
    return Order(
        order_id="ord-001",
        user_id="synthetic-user-001",
        merchant_id="merchant-001",
        status=OrderStatus.DELIVERED,
        paid_amount=Decimal("58.00"),
        coupon_id="coupon-001",
        city="Shanghai",
        business_type=BusinessType.FOOD_DELIVERY,
        created_at=BASE_TIME,
        policy_version="2026.1",
    )


def build_seed_coupon() -> Coupon:
    return Coupon(
        coupon_id="coupon-001",
        user_id="synthetic-user-001",
        status=CouponStatus.USED,
        order_id="ord-001",
    )


def generate_dataset(seed: int, order_count: int) -> SyntheticDataset:
    if order_count < 1:
        raise ValueError("order_count must be positive")
    random = Random(seed)
    orders: list[Order] = []
    payments: list[PaymentRecord] = []
    coupons: list[Coupon] = []
    merchants: dict[str, Merchant] = {}
    deliveries: list[Delivery] = []
    statuses = tuple(OrderStatus)
    cities = ("Shanghai", "Beijing", "Shenzhen")

    for index in range(order_count):
        suffix = f"{index + 1:04d}"
        order_id = f"synthetic-order-{suffix}"
        user_id = f"synthetic-user-{random.randint(1, max(2, order_count // 2)):04d}"
        merchant_id = f"synthetic-merchant-{random.randint(1, 5):03d}"
        city = random.choice(cities)
        amount = Decimal(random.randint(1200, 12000)) / Decimal("100")
        coupon_id = f"synthetic-coupon-{suffix}" if random.random() < 0.5 else None
        created_at = BASE_TIME + timedelta(minutes=index)
        status = random.choice(statuses)
        order = Order(
            order_id=order_id,
            user_id=user_id,
            merchant_id=merchant_id,
            status=status,
            paid_amount=amount,
            coupon_id=coupon_id,
            city=city,
            business_type=random.choice(tuple(BusinessType)),
            created_at=created_at,
            policy_version="2026.1",
        )
        orders.append(order)
        payments.append(
            PaymentRecord(
                payment_id=f"synthetic-payment-{suffix}",
                order_id=order_id,
                amount=amount,
                status=PaymentStatus.CAPTURED,
                charged_at=created_at,
            )
        )
        if coupon_id is not None:
            coupons.append(
                Coupon(
                    coupon_id=coupon_id,
                    user_id=user_id,
                    status=CouponStatus.USED,
                    order_id=order_id,
                )
            )
        merchants.setdefault(
            merchant_id,
            Merchant(merchant_id, MerchantStatus.OPEN, city),
        )
        delivery_status = (
            DeliveryStatus.DELIVERED
            if status is OrderStatus.DELIVERED
            else DeliveryStatus.UNASSIGNED
        )
        deliveries.append(Delivery(order_id, delivery_status, created_at + timedelta(hours=1)))

    return SyntheticDataset(
        tuple(orders),
        tuple(payments),
        tuple(coupons),
        tuple(merchants.values()),
        tuple(deliveries),
    )
