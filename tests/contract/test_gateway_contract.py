from dataclasses import replace
from decimal import Decimal

import pytest

from servicepilot.domain.models import OrderStatus
from servicepilot.domain.repositories import InMemoryRepository
from servicepilot.domain.services import TransactionService
from servicepilot.domain.synthetic import (
    build_seed_coupon,
    build_seed_order,
    generate_dataset,
)
from servicepilot.mcp_gateway.errors import ToolErrorCode
from servicepilot.mcp_gateway.faults import FaultKind, FaultPlan
from servicepilot.mcp_gateway.gateway import ReliableToolGateway
from servicepilot.mcp_servers.registry import ServiceRegistry
from servicepilot.policies.engine import PolicyEngine


def build_gateway(
    faults: FaultPlan | None = None, tool_budget: int = 20
) -> tuple[ReliableToolGateway, InMemoryRepository]:
    repository = InMemoryRepository()
    dataset = generate_dataset(seed=11, order_count=5)
    repository.load_dataset(dataset)
    repository.add_order(build_seed_order())
    repository.add_coupon(build_seed_coupon())
    transactions = TransactionService(repository, PolicyEngine.default())
    registry = ServiceRegistry(repository, transactions, PolicyEngine.default())
    return (
        ReliableToolGateway(
            registry,
            timeout_seconds=0.05,
            max_retries=2,
            tool_budget=tool_budget,
            faults=faults,
            backoff=lambda _: None,
        ),
        repository,
    )


@pytest.mark.asyncio
async def test_schema_error_is_typed_and_not_retried() -> None:
    gateway, _ = build_gateway()

    result = await gateway.call("get_order", {}, trace_id="trace-schema")

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.VALIDATION
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_transient_failure_recovers_with_bounded_retry() -> None:
    faults = FaultPlan({"get_order": [FaultKind.TRANSIENT]})
    gateway, _ = build_gateway(faults)

    result = await gateway.call("get_order", {"order_id": "ord-001"}, trace_id="trace-retry")

    assert result.ok is True
    assert result.attempts == 2
    assert result.trace_id == "trace-retry"
    assert result.duration_ms >= 0


@pytest.mark.asyncio
async def test_timeout_exhaustion_is_stable() -> None:
    faults = FaultPlan({"get_order": [FaultKind.TIMEOUT, FaultKind.TIMEOUT, FaultKind.TIMEOUT]})
    gateway, _ = build_gateway(faults)

    result = await gateway.call("get_order", {"order_id": "ord-001"}, trace_id="trace-timeout")

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.TIMEOUT
    assert result.attempts == 3


@pytest.mark.asyncio
async def test_empty_result_fault_is_classified() -> None:
    gateway, _ = build_gateway(FaultPlan({"get_order": [FaultKind.EMPTY_RESULT]}))

    result = await gateway.call("get_order", {"order_id": "ord-001"}, trace_id="trace-empty")

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.EMPTY_RESULT


@pytest.mark.asyncio
async def test_partial_result_fault_is_classified() -> None:
    gateway, _ = build_gateway(FaultPlan({"get_order": [FaultKind.PARTIAL_RESULT]}))

    result = await gateway.call("get_order", {"order_id": "ord-001"}, trace_id="trace-partial")

    assert result.ok is False
    assert result.error is not None
    assert result.error.code is ToolErrorCode.PARTIAL_RESULT


@pytest.mark.asyncio
async def test_tool_budget_stops_additional_calls() -> None:
    gateway, _ = build_gateway(tool_budget=1)
    first = await gateway.call("get_order", {"order_id": "ord-001"}, trace_id="trace-budget")
    second = await gateway.call("get_order", {"order_id": "ord-001"}, trace_id="trace-budget")

    assert first.ok is True
    assert second.error is not None
    assert second.error.code is ToolErrorCode.BUDGET_EXCEEDED


@pytest.mark.asyncio
async def test_lost_refund_response_retries_without_duplicate_write() -> None:
    faults = FaultPlan({"create_refund_request": [FaultKind.LOST_RESPONSE]})
    gateway, repository = build_gateway(faults)
    preview = await gateway.call(
        "preview_refund",
        {
            "order_id": "ord-001",
            "reason": "missing_item",
            "requested_amount": "12.00",
        },
        trace_id="trace-lost",
    )
    assert preview.ok is True
    assert preview.data is not None

    result = await gateway.call(
        "create_refund_request",
        {
            "order_id": "ord-001",
            "reason": "missing_item",
            "requested_amount": "12.00",
            "confirmation_token": preview.data["confirmation_token"],
            "idempotency_key": "refund-lost-001",
            "expected_version": 1,
        },
        trace_id="trace-lost",
    )

    assert result.ok is True
    assert result.attempts == 2
    assert len(repository.list_refunds("ord-001")) == 1


@pytest.mark.asyncio
async def test_version_conflict_is_not_retried() -> None:
    gateway, repository = build_gateway()
    repository.save_order(replace(build_seed_order(), status=OrderStatus.DELIVERED, version=2))
    preview = await gateway.call(
        "preview_refund",
        {
            "order_id": "ord-001",
            "reason": "missing_item",
            "requested_amount": str(Decimal("12.00")),
        },
        trace_id="trace-version",
    )
    assert preview.data is not None

    result = await gateway.call(
        "create_refund_request",
        {
            "order_id": "ord-001",
            "reason": "missing_item",
            "requested_amount": "12.00",
            "confirmation_token": preview.data["confirmation_token"],
            "idempotency_key": "refund-version-001",
            "expected_version": 1,
        },
        trace_id="trace-version",
    )

    assert result.error is not None
    assert result.error.code is ToolErrorCode.VERSION_CONFLICT
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_delivery_issue_is_idempotent_and_audited() -> None:
    gateway, repository = build_gateway()
    arguments = {
        "order_id": "ord-001",
        "issue_type": "delivery_delay",
        "idempotency_key": "delivery-issue-001",
    }

    first = await gateway.call("report_delivery_issue", arguments, trace_id="trace-issue")
    second = await gateway.call("report_delivery_issue", arguments, trace_id="trace-issue")

    assert first.ok is True
    assert second.data == first.data
    matching_audits = [
        event for event in repository.list_audit_events() if event.action == "report_delivery_issue"
    ]
    assert len(matching_audits) == 1
