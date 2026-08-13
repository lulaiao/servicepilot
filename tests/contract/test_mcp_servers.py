import pytest
from mcp import Client

from servicepilot.mcp_servers.factory import build_seeded_servers

pytestmark = pytest.mark.asyncio


async def _tool_names(server_name: str) -> set[str]:
    servers, _ = build_seeded_servers()
    async with Client(servers[server_name]) as client:
        result = await client.list_tools()
    return {tool.name for tool in result.tools}


async def test_order_mcp_tools_are_discoverable() -> None:
    assert await _tool_names("order") == {
        "get_order",
        "list_recent_orders",
        "preview_cancel",
        "cancel_order",
        "preview_reschedule",
        "reschedule_order",
    }


async def test_refund_coupon_policy_and_delivery_tools_are_discoverable() -> None:
    assert await _tool_names("payment_refund") == {
        "get_payment_records",
        "check_refund_eligibility",
        "preview_refund",
        "create_refund_request",
        "get_refund_status",
    }
    assert await _tool_names("coupon") == {
        "get_coupon_status",
        "check_coupon_restore_eligibility",
        "preview_coupon_restore",
        "restore_coupon",
    }
    assert await _tool_names("policy") == {
        "search_policy",
        "get_policy_section",
        "verify_policy_applicability",
    }
    assert await _tool_names("merchant_delivery") == {
        "get_merchant_status",
        "get_delivery_status",
        "report_delivery_issue",
        "create_handoff_ticket",
    }


async def test_in_memory_mcp_call_returns_structured_order() -> None:
    servers, _ = build_seeded_servers()
    async with Client(servers["order"], raise_exceptions=True) as client:
        result = await client.call_tool("get_order", {"order_id": "ord-001"})

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["order_id"] == "ord-001"
    assert result.structured_content["status"] == "DELIVERED"


async def test_each_business_server_executes_a_structured_read() -> None:
    servers, _ = build_seeded_servers()
    calls = (
        (
            "payment_refund",
            "check_refund_eligibility",
            {
                "order_id": "ord-001",
                "reason": "missing_item",
                "requested_amount": "12.00",
            },
        ),
        (
            "coupon",
            "get_coupon_status",
            {
                "user_id": "synthetic-user-001",
                "coupon_id": "coupon-001",
            },
        ),
        (
            "policy",
            "get_policy_section",
            {
                "evidence_id": "policy_partial_refund_2026_1_section_3",
            },
        ),
        (
            "merchant_delivery",
            "get_delivery_status",
            {
                "order_id": "ord-001",
            },
        ),
    )

    for server_name, tool_name, arguments in calls:
        async with Client(servers[server_name], raise_exceptions=True) as client:
            result = await client.call_tool(tool_name, arguments)
        assert result.is_error is False
        assert result.structured_content
