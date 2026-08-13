"""Official MCP SDK v2 server factories backed by deterministic services."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from mcp.server import MCPServer

from servicepilot.domain.models import (
    Delivery,
    DeliveryStatus,
    Merchant,
    MerchantStatus,
)
from servicepilot.domain.repositories import InMemoryRepository
from servicepilot.domain.services import TransactionService
from servicepilot.domain.synthetic import (
    build_seed_coupon,
    build_seed_order,
    generate_dataset,
)
from servicepilot.mcp_servers.registry import ServiceRegistry
from servicepilot.policies.engine import PolicyEngine


def build_servers(registry: ServiceRegistry) -> dict[str, MCPServer]:
    order = MCPServer("ServicePilot Order", version="0.2.0")
    payment_refund = MCPServer("ServicePilot Payment Refund", version="0.2.0")
    coupon = MCPServer("ServicePilot Coupon", version="0.2.0")
    policy = MCPServer("ServicePilot Policy", version="0.2.0")
    merchant_delivery = MCPServer("ServicePilot Merchant Delivery", version="0.2.0")

    @order.tool()
    async def get_order(order_id: str) -> dict[str, Any]:
        """Get authoritative order state."""
        return registry.call("get_order", {"order_id": order_id})

    @order.tool()
    async def list_recent_orders(user_id: str, limit: int = 10) -> dict[str, Any]:
        """List a user's recent synthetic orders."""
        return registry.call("list_recent_orders", {"user_id": user_id, "limit": limit})

    @order.tool()
    async def preview_cancel(order_id: str) -> dict[str, Any]:
        """Preview cancellation and return a confirmation token."""
        return registry.call("preview_cancel", {"order_id": order_id})

    @order.tool()
    async def cancel_order(
        order_id: str,
        confirmation_token: str,
        idempotency_key: str,
        expected_version: int,
    ) -> dict[str, Any]:
        """Execute a confirmed idempotent cancellation."""
        return registry.call(
            "cancel_order",
            {
                "order_id": order_id,
                "confirmation_token": confirmation_token,
                "idempotency_key": idempotency_key,
                "expected_version": expected_version,
            },
        )

    @order.tool()
    async def preview_reschedule(order_id: str, new_time: datetime) -> dict[str, Any]:
        """Preview a delivery or appointment reschedule."""
        return registry.call(
            "preview_reschedule",
            {"order_id": order_id, "new_time": new_time},
        )

    @order.tool()
    async def reschedule_order(
        order_id: str,
        new_time: datetime,
        confirmation_token: str,
        idempotency_key: str,
        expected_version: int,
    ) -> dict[str, Any]:
        """Execute a confirmed idempotent reschedule."""
        return registry.call(
            "reschedule_order",
            {
                "order_id": order_id,
                "new_time": new_time,
                "confirmation_token": confirmation_token,
                "idempotency_key": idempotency_key,
                "expected_version": expected_version,
            },
        )

    @payment_refund.tool()
    async def get_payment_records(order_id: str) -> dict[str, Any]:
        """Get payment records for an order."""
        return registry.call("get_payment_records", {"order_id": order_id})

    @payment_refund.tool()
    async def check_refund_eligibility(
        order_id: str, reason: str, requested_amount: Decimal
    ) -> dict[str, Any]:
        """Check deterministic refund policy without writing state."""
        return registry.call(
            "check_refund_eligibility",
            {
                "order_id": order_id,
                "reason": reason,
                "requested_amount": requested_amount,
            },
        )

    @payment_refund.tool()
    async def preview_refund(
        order_id: str, reason: str, requested_amount: Decimal
    ) -> dict[str, Any]:
        """Preview a refund and return evidence and confirmation."""
        return registry.call(
            "preview_refund",
            {
                "order_id": order_id,
                "reason": reason,
                "requested_amount": requested_amount,
            },
        )

    @payment_refund.tool()
    async def create_refund_request(
        order_id: str,
        reason: str,
        requested_amount: Decimal,
        confirmation_token: str,
        idempotency_key: str,
        expected_version: int,
    ) -> dict[str, Any]:
        """Execute a confirmed idempotent refund request."""
        return registry.call(
            "create_refund_request",
            {
                "order_id": order_id,
                "reason": reason,
                "requested_amount": requested_amount,
                "confirmation_token": confirmation_token,
                "idempotency_key": idempotency_key,
                "expected_version": expected_version,
            },
        )

    @payment_refund.tool()
    async def get_refund_status(refund_id: str) -> dict[str, Any]:
        """Get authoritative refund status."""
        return registry.call("get_refund_status", {"refund_id": refund_id})

    @coupon.tool()
    async def get_coupon_status(user_id: str, coupon_id: str) -> dict[str, Any]:
        """Get a user's coupon state."""
        return registry.call(
            "get_coupon_status",
            {"user_id": user_id, "coupon_id": coupon_id},
        )

    @coupon.tool()
    async def check_coupon_restore_eligibility(
        order_id: str,
    ) -> dict[str, Any]:
        """Check coupon restoration policy."""
        return registry.call("check_coupon_restore_eligibility", {"order_id": order_id})

    @coupon.tool()
    async def preview_coupon_restore(order_id: str) -> dict[str, Any]:
        """Preview coupon restoration."""
        return registry.call("preview_coupon_restore", {"order_id": order_id})

    @coupon.tool()
    async def restore_coupon(
        order_id: str,
        confirmation_token: str,
        idempotency_key: str,
        expected_order_version: int,
    ) -> dict[str, Any]:
        """Execute confirmed idempotent coupon restoration."""
        return registry.call(
            "restore_coupon",
            {
                "order_id": order_id,
                "confirmation_token": confirmation_token,
                "idempotency_key": idempotency_key,
                "expected_order_version": expected_order_version,
            },
        )

    @policy.tool()
    async def search_policy(
        query: str,
        metadata_filters: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Search the Phase 1 policy corpus."""
        return registry.call(
            "search_policy",
            {
                "query": query,
                "metadata_filters": metadata_filters or {},
                "top_k": top_k,
            },
        )

    @policy.tool()
    async def get_policy_section(evidence_id: str) -> dict[str, Any]:
        """Get a policy section by stable evidence ID."""
        return registry.call("get_policy_section", {"evidence_id": evidence_id})

    @policy.tool()
    async def verify_policy_applicability(evidence_ids: list[str], order_id: str) -> dict[str, Any]:
        """Verify evidence IDs and policy version against an order."""
        return registry.call(
            "verify_policy_applicability",
            {"evidence_ids": evidence_ids, "order_id": order_id},
        )

    @merchant_delivery.tool()
    async def get_merchant_status(merchant_id: str) -> dict[str, Any]:
        """Get authoritative merchant status."""
        return registry.call("get_merchant_status", {"merchant_id": merchant_id})

    @merchant_delivery.tool()
    async def get_delivery_status(order_id: str) -> dict[str, Any]:
        """Get authoritative delivery status."""
        return registry.call("get_delivery_status", {"order_id": order_id})

    @merchant_delivery.tool()
    async def report_delivery_issue(
        order_id: str, issue_type: str, idempotency_key: str
    ) -> dict[str, Any]:
        """Create an idempotent delivery issue."""
        return registry.call(
            "report_delivery_issue",
            {
                "order_id": order_id,
                "issue_type": issue_type,
                "idempotency_key": idempotency_key,
            },
        )

    @merchant_delivery.tool()
    async def create_handoff_ticket(
        order_id: str, context: str, reason: str, idempotency_key: str
    ) -> dict[str, Any]:
        """Create an idempotent human handoff ticket."""
        return registry.call(
            "create_handoff_ticket",
            {
                "order_id": order_id,
                "context": context,
                "reason": reason,
                "idempotency_key": idempotency_key,
            },
        )

    return {
        "order": order,
        "payment_refund": payment_refund,
        "coupon": coupon,
        "policy": policy,
        "merchant_delivery": merchant_delivery,
    }


def build_seeded_servers() -> tuple[dict[str, MCPServer], ServiceRegistry]:
    repository = InMemoryRepository()
    repository.load_dataset(generate_dataset(seed=11, order_count=5))
    seed_order = build_seed_order()
    repository.add_order(seed_order)
    repository.add_coupon(build_seed_coupon())
    repository.add_merchant(Merchant(seed_order.merchant_id, MerchantStatus.OPEN, seed_order.city))
    repository.add_delivery(
        Delivery(
            seed_order.order_id,
            DeliveryStatus.DELIVERED,
            datetime(2026, 1, 1, 13, 0, tzinfo=UTC),
        )
    )
    policies = PolicyEngine.default()
    registry = ServiceRegistry(repository, TransactionService(repository, policies), policies)
    return build_servers(registry), registry
