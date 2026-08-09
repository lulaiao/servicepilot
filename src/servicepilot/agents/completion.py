"""Deterministic evidence gate for Agent completion claims."""

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.models import Intent, TraceEvent

_COMPLETION_TOOL: dict[Intent, str | None] = {
    Intent.ORDER_QUERY: "get_order",
    Intent.CANCEL_ORDER: "cancel_order",
    Intent.FULL_REFUND: "create_refund_request",
    Intent.PARTIAL_REFUND: "create_refund_request",
    Intent.MISSING_OR_WRONG_ITEM: "create_refund_request",
    Intent.DUPLICATE_CHARGE: "create_refund_request",
    Intent.DELIVERY_DELAY: "report_delivery_issue",
    Intent.COUPON_ISSUE: "restore_coupon",
    Intent.RESCHEDULE: "reschedule_order",
    Intent.COMPLAINT_ESCALATION: "create_handoff_ticket",
    Intent.OUT_OF_SCOPE: None,
    Intent.MULTI_INTENT: None,
}


class CompletionDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    required_tools: tuple[str, ...]
    missing_tools: tuple[str, ...]


class OutputCompletionVerifier:
    def verify(
        self, required_intents: tuple[Intent, ...], events: tuple[TraceEvent, ...]
    ) -> CompletionDecision:
        required = tuple(
            dict.fromkeys(
                tool
                for intent in required_intents
                if (tool := _COMPLETION_TOOL[intent]) is not None
            )
        )
        successful = {
            event.tool_name
            for event in events
            if event.tool_name
            and event.result
            and event.result.get("ok") is True
        }
        missing = tuple(tool for tool in required if tool not in successful)
        return CompletionDecision(
            allowed=not missing, required_tools=required, missing_tools=missing
        )
