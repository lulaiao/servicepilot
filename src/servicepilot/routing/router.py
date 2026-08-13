"""Stateful role router evaluated on every pending action and observation."""

from servicepilot.eval.models import Intent
from servicepilot.mcp_gateway.errors import ToolErrorCode
from servicepilot.routing.models import (
    AgentRole,
    DialogueState,
    RouteDecision,
)


class StatefulRouter:
    def route(self, state: DialogueState) -> RouteDecision:
        if state.intent.injection_detected:
            return RouteDecision(
                role=AgentRole.ESCALATION,
                reason="prompt injection or policy bypass attempt",
                should_stop=True,
            )
        if state.tool_budget_remaining <= 0 or state.monitor_alerts:
            return RouteDecision(
                role=AgentRole.ESCALATION,
                reason="budget or monitor safety boundary",
                should_stop=True,
            )
        if any(
            item.error_code
            in {
                ToolErrorCode.VERSION_CONFLICT,
                ToolErrorCode.CONFIRMATION_REQUIRED,
            }
            for item in state.failed_tools
        ):
            return RouteDecision(
                role=AgentRole.COORDINATOR,
                reason="state changed; re-read and obtain a new confirmation",
                should_clarify=True,
            )
        if state.intent.needs_clarification and "order_id" not in state.confirmed_slots:
            return RouteDecision(
                role=AgentRole.COORDINATOR,
                reason="required order slot is missing",
                should_clarify=True,
            )
        if state.pending_action and state.pending_action.startswith("preview_"):
            return RouteDecision(
                role=AgentRole.POLICY,
                reason="preview requires policy evidence before write",
            )
        if state.pending_action in {
            "get_order",
            "list_recent_orders",
            "preview_reschedule",
            "reschedule_order",
        }:
            return RouteDecision(
                role=AgentRole.ORDER,
                reason="order state or scheduling action",
            )
        if state.pending_action in {
            "cancel_order",
            "create_refund_request",
            "restore_coupon",
            "get_payment_records",
        }:
            return RouteDecision(
                role=AgentRole.AFTER_SALES,
                reason="after-sales transactional action",
            )
        if state.pending_action in {
            "create_handoff_ticket",
            "report_delivery_issue",
        }:
            role = (
                AgentRole.ESCALATION
                if state.pending_action == "create_handoff_ticket"
                else AgentRole.ORDER
            )
            return RouteDecision(role=role, reason="service recovery action")
        if state.intent.primary_intent is Intent.OUT_OF_SCOPE:
            return RouteDecision(
                role=AgentRole.ESCALATION,
                reason="request is outside controlled action space",
                should_stop=True,
            )
        return RouteDecision(
            role=AgentRole.VERIFIER,
            reason="no pending action; verify completion against observations",
        )


ROLE_INSTRUCTIONS: dict[AgentRole, str] = {
    AgentRole.COORDINATOR: "Maintain goal, slots, budgets and the next safe action.",
    AgentRole.ORDER: "Handle order state, delivery status and rescheduling.",
    AgentRole.AFTER_SALES: "Handle cancellation, refund, coupon and payment actions.",
    AgentRole.POLICY: "Require applicable evidence before high-risk writes.",
    AgentRole.ESCALATION: "Stop unsafe flows or create a complete human handoff.",
    AgentRole.VERIFIER: "Verify final state; never execute a high-risk write.",
}
