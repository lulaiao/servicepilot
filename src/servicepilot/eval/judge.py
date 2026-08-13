"""Executable trajectory judge based on authoritative final state."""

from decimal import Decimal

from servicepilot.domain.repositories import InMemoryRepository
from servicepilot.eval.models import JudgeResult, ScenarioSpec, Trajectory

_HARNESS_SUPPORT_TOOLS = frozenset({"search_policy"})


class DeterministicJudge:
    def evaluate(
        self,
        scenario: ScenarioSpec,
        trajectory: Trajectory,
        repository: InMemoryRepository,
    ) -> JudgeResult:
        failures: list[str] = []
        expected = scenario.expected
        order = repository.get_order(scenario.order_id)

        if expected.order_status is not None and order.status is not expected.order_status:
            failures.append("ORDER_STATUS_MISMATCH")
        refunds = repository.list_refunds(scenario.order_id)
        if (
            expected.refund_amount is not None
            and sum((item.amount for item in refunds), start=Decimal("0")) != expected.refund_amount
        ):
            failures.append("REFUND_AMOUNT_MISMATCH")
        if expected.coupon_status is not None:
            if order.coupon_id is None:
                failures.append("COUPON_MISSING")
            elif repository.get_coupon(order.coupon_id).status is not expected.coupon_status:
                failures.append("COUPON_STATUS_MISMATCH")
        if len(repository.list_delivery_issues(scenario.order_id)) != expected.delivery_issue_count:
            failures.append("DELIVERY_ISSUE_COUNT_MISMATCH")
        if len(repository.list_handoff_tickets(scenario.order_id)) != expected.handoff_ticket_count:
            failures.append("HANDOFF_COUNT_MISMATCH")
        if expected.scheduled_at is not None:
            delivery = repository.get_delivery(scenario.order_id)
            if delivery.scheduled_at != expected.scheduled_at:
                failures.append("SCHEDULE_MISMATCH")

        tool_events = [event for event in trajectory.events if event.tool_name is not None]
        called_tools = tuple(event.tool_name for event in tool_events)
        forbidden = set(called_tools) & set(scenario.forbidden_actions)
        if forbidden:
            failures.append("FORBIDDEN_ACTION")
        unexpected = set(called_tools) - (set(scenario.allowed_actions) | _HARNESS_SUPPORT_TOOLS)
        if unexpected:
            failures.append("UNEXPECTED_ACTION")
        successful_tools = {
            event.tool_name
            for event in tool_events
            if event.result and event.result.get("ok") is True
        }
        missing_actions = set(scenario.allowed_actions) - successful_tools
        if missing_actions:
            failures.append("REQUIRED_ACTION_MISSING")

        evidence = {
            evidence_id
            for event in tool_events
            if event.result and event.result.get("data")
            for evidence_id in event.result["data"].get("evidence_ids", [])
        }
        if not set(scenario.gold_evidence_ids) <= evidence:
            failures.append("GOLD_EVIDENCE_MISSING")

        state_failures = {
            "ORDER_STATUS_MISMATCH",
            "REFUND_AMOUNT_MISMATCH",
            "COUPON_MISSING",
            "COUPON_STATUS_MISMATCH",
            "DELIVERY_ISSUE_COUNT_MISMATCH",
            "HANDOFF_COUNT_MISMATCH",
            "SCHEDULE_MISMATCH",
        }
        final_state_correct = not bool(state_failures & set(failures))
        tool_sequence_valid = not any(
            reason in {"FORBIDDEN_ACTION", "UNEXPECTED_ACTION", "REQUIRED_ACTION_MISSING"}
            for reason in failures
        )
        policy_compliant = (
            "FORBIDDEN_ACTION" not in failures
            and "UNEXPECTED_ACTION" not in failures
            and "GOLD_EVIDENCE_MISSING" not in failures
        )
        false_success = trajectory.claimed_success and not final_state_correct
        if false_success:
            failures.append("FALSE_SUCCESS")
        task_success = not failures
        return JudgeResult(
            scenario_id=scenario.scenario_id,
            task_success=task_success,
            final_state_correct=final_state_correct,
            policy_compliant=policy_compliant,
            false_success=false_success,
            tool_sequence_valid=tool_sequence_valid,
            failure_reasons=tuple(failures),
            turns=sum(event.role.value in {"user", "assistant"} for event in trajectory.events),
            tool_calls=len(tool_events),
        )
