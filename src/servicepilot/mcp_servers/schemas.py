"""Pydantic request contracts shared by MCP servers and the gateway."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
PositiveVersion = Annotated[int, Field(ge=1)]


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetOrderRequest(ToolRequest):
    order_id: NonBlank


class ListRecentOrdersRequest(ToolRequest):
    user_id: NonBlank
    limit: Annotated[int, Field(ge=1, le=50)] = 10


class PreviewCancelRequest(GetOrderRequest):
    pass


class CancelOrderRequest(GetOrderRequest):
    confirmation_token: NonBlank
    idempotency_key: NonBlank
    expected_version: PositiveVersion


class PreviewRescheduleRequest(GetOrderRequest):
    new_time: datetime


class RescheduleOrderRequest(PreviewRescheduleRequest):
    confirmation_token: NonBlank
    idempotency_key: NonBlank
    expected_version: PositiveVersion


class GetPaymentRecordsRequest(GetOrderRequest):
    pass


class RefundEligibilityRequest(GetOrderRequest):
    reason: NonBlank
    requested_amount: PositiveMoney


class CreateRefundRequest(RefundEligibilityRequest):
    confirmation_token: NonBlank
    idempotency_key: NonBlank
    expected_version: PositiveVersion


class GetRefundStatusRequest(ToolRequest):
    refund_id: NonBlank


class GetCouponStatusRequest(ToolRequest):
    user_id: NonBlank
    coupon_id: NonBlank


class CouponEligibilityRequest(GetOrderRequest):
    pass


class RestoreCouponRequest(GetOrderRequest):
    confirmation_token: NonBlank
    idempotency_key: NonBlank
    expected_order_version: PositiveVersion


class SearchPolicyRequest(ToolRequest):
    query: NonBlank
    metadata_filters: dict[str, Any] = Field(default_factory=dict)
    top_k: Annotated[int, Field(ge=1, le=20)] = 5


class GetPolicySectionRequest(ToolRequest):
    evidence_id: NonBlank


class VerifyPolicyRequest(ToolRequest):
    evidence_ids: Annotated[list[NonBlank], Field(min_length=1, max_length=20)]
    order_id: NonBlank


class GetMerchantStatusRequest(ToolRequest):
    merchant_id: NonBlank


class GetDeliveryStatusRequest(GetOrderRequest):
    pass


class ReportDeliveryIssueRequest(GetOrderRequest):
    issue_type: NonBlank
    idempotency_key: NonBlank


class CreateHandoffTicketRequest(GetOrderRequest):
    context: NonBlank
    reason: NonBlank
    idempotency_key: NonBlank
