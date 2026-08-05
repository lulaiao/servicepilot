import pytest
from pydantic import ValidationError

from servicepilot.mcp_servers.schemas import (
    CreateRefundRequest,
    GetOrderRequest,
    SearchPolicyRequest,
)


def test_order_id_rejects_blank_values() -> None:
    with pytest.raises(ValidationError):
        GetOrderRequest(order_id="   ")


def test_refund_request_requires_positive_amount_and_nonempty_keys() -> None:
    with pytest.raises(ValidationError):
        CreateRefundRequest(
            order_id="ord-001",
            reason="missing_item",
            requested_amount="0",
            confirmation_token="token",
            idempotency_key="",
            expected_version=1,
        )


def test_policy_top_k_is_bounded() -> None:
    with pytest.raises(ValidationError):
        SearchPolicyRequest(query="refund", top_k=101)

