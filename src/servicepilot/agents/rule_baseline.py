"""Deterministic single-agent baseline for executable Phase 3 evaluation."""

from typing import Any

from servicepilot.eval.models import (
    Intent,
    ScenarioSpec,
    TraceEvent,
    TraceRole,
    Trajectory,
)
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.mcp_gateway.gateway import ReliableToolGateway, ToolResult


class RuleBasedSingleAgent:
    async def run(
        self,
        scenario: ScenarioSpec,
        simulator: FSMUserSimulator,
        gateway: ReliableToolGateway,
    ) -> Trajectory:
        trace_id = f"trajectory-{scenario.scenario_id}"
        events: list[TraceEvent] = []
        user_text = simulator.start()
        self._event(events, TraceRole.USER, "message", user_text)
        intents = self.detect_intents(user_text)

        if intents == (Intent.OUT_OF_SCOPE,):
            message = "这个请求不属于本地生活订单售后范围，我不会执行订单写操作。"
            self._event(events, TraceRole.ASSISTANT, "message", message)
            simulator.finish()
            return self._trajectory(scenario, trace_id, events, False, message, intents)

        question = "请提供需要处理的订单号。"
        self._event(events, TraceRole.ASSISTANT, "clarification", question)
        order_answer = simulator.answer_order_question()
        self._event(events, TraceRole.USER, "message", order_answer)
        order_id = order_answer.rsplit(" ", 1)[-1]

        successes: list[bool] = []
        for intent in intents:
            successes.append(
                await self._execute_intent(
                    intent,
                    order_id,
                    user_text,
                    simulator,
                    gateway,
                    trace_id,
                    events,
                )
            )
        claimed_success = bool(successes) and all(successes)
        message = (
            "已按确认完成处理，结果以系统状态为准。"
            if claimed_success
            else "处理未完成，未对失败步骤作完成承诺。"
        )
        self._event(events, TraceRole.ASSISTANT, "final", message)
        simulator.finish()
        return self._trajectory(scenario, trace_id, events, claimed_success, message, intents)

    def detect_intents(self, text: str) -> tuple[Intent, ...]:
        if "忽略规则" in text or "直接修改数据库" in text:
            return (Intent.OUT_OF_SCOPE,)
        if ("延迟" in text or "超时" in text or "太慢" in text) and (
            "投诉" in text or "人工" in text
        ):
            return (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION)
        if "优惠券" in text or "用掉的券" in text:
            return (Intent.COUPON_ISSUE,)
        if "取消" in text or "不要了" in text or "刚下的单退掉" in text:
            return (Intent.CANCEL_ORDER,)
        if "修改" in text or "改到" in text or "改一下" in text:
            return (Intent.RESCHEDULE,)
        if "投诉" in text or "人工" in text or "工单" in text:
            return (Intent.COMPLAINT_ESCALATION,)
        if "重复" in text or "两次" in text:
            return (Intent.DUPLICATE_CHARGE,)
        if "少了" in text or "漏送" in text or "不对" in text:
            return (Intent.MISSING_OR_WRONG_ITEM,)
        if "部分退款" in text or "退我12" in text or "退12" in text:
            return (Intent.PARTIAL_REFUND,)
        if "全额" in text or "全部退" in text or "整单退款" in text:
            return (Intent.FULL_REFUND,)
        if "延迟" in text or "超时" in text or "太慢" in text:
            return (Intent.DELIVERY_DELAY,)
        if "订单状态" in text or "到哪" in text or "没消息" in text:
            return (Intent.ORDER_QUERY,)
        return (Intent.OUT_OF_SCOPE,)

    async def _execute_intent(
        self,
        intent: Intent,
        order_id: str,
        user_text: str,
        simulator: FSMUserSimulator,
        gateway: ReliableToolGateway,
        trace_id: str,
        events: list[TraceEvent],
    ) -> bool:
        if intent is Intent.ORDER_QUERY:
            return (
                await self._call(
                    gateway,
                    trace_id,
                    events,
                    "get_order",
                    {"order_id": order_id},
                )
            ).ok
        if intent is Intent.CANCEL_ORDER:
            return await self._confirmed_write(
                simulator,
                gateway,
                trace_id,
                events,
                "preview_cancel",
                "cancel_order",
                {"order_id": order_id},
                {"order_id": order_id},
            )
        if intent in {
            Intent.FULL_REFUND,
            Intent.PARTIAL_REFUND,
            Intent.MISSING_OR_WRONG_ITEM,
            Intent.DUPLICATE_CHARGE,
        }:
            question = "请确认退款原因和期望退款金额。"
            self._event(events, TraceRole.ASSISTANT, "clarification", question)
            if not simulator.has_refund_details():
                self._event(
                    events,
                    TraceRole.USER,
                    "slot_unavailable",
                    "当前无法提供退款原因或金额。",
                )
                return False
            reason, amount = simulator.refund_details()
            self._event(
                events,
                TraceRole.USER,
                "slot_answer",
                f"原因是 {reason}，金额 {amount}",
            )
            common = {
                "order_id": order_id,
                "reason": reason,
                "requested_amount": str(amount),
            }
            return await self._confirmed_write(
                simulator,
                gateway,
                trace_id,
                events,
                "preview_refund",
                "create_refund_request",
                common,
                common,
            )
        if intent is Intent.COUPON_ISSUE:
            return await self._confirmed_write(
                simulator,
                gateway,
                trace_id,
                events,
                "preview_coupon_restore",
                "restore_coupon",
                {"order_id": order_id},
                {"order_id": order_id},
                version_key="expected_order_version",
            )
        if intent is Intent.RESCHEDULE:
            question = "请确认新的预约或配送时间。"
            self._event(events, TraceRole.ASSISTANT, "clarification", question)
            if not simulator.has_reschedule_time():
                self._event(
                    events,
                    TraceRole.USER,
                    "slot_unavailable",
                    "当前无法提供新的预约或配送时间。",
                )
                return False
            new_time = simulator.reschedule_time()
            self._event(
                events,
                TraceRole.USER,
                "slot_answer",
                new_time.isoformat(),
            )
            common = {
                "order_id": order_id,
                "new_time": new_time.isoformat(),
            }
            return await self._confirmed_write(
                simulator,
                gateway,
                trace_id,
                events,
                "preview_reschedule",
                "reschedule_order",
                common,
                common,
            )
        if intent is Intent.DELIVERY_DELAY:
            result = await self._call(
                gateway,
                trace_id,
                events,
                "report_delivery_issue",
                {
                    "order_id": order_id,
                    "issue_type": "delivery_delay",
                    "idempotency_key": f"{trace_id}-delivery",
                },
            )
            return result.ok
        if intent is Intent.COMPLAINT_ESCALATION:
            result = await self._call(
                gateway,
                trace_id,
                events,
                "create_handoff_ticket",
                {
                    "order_id": order_id,
                    "context": user_text,
                    "reason": "user_requested_escalation",
                    "idempotency_key": f"{trace_id}-handoff",
                },
            )
            return result.ok
        return False

    async def _confirmed_write(
        self,
        simulator: FSMUserSimulator,
        gateway: ReliableToolGateway,
        trace_id: str,
        events: list[TraceEvent],
        preview_tool: str,
        execute_tool: str,
        preview_arguments: dict[str, Any],
        execute_arguments: dict[str, Any],
        *,
        version_key: str = "expected_version",
    ) -> bool:
        preview = await self._call(gateway, trace_id, events, preview_tool, preview_arguments)
        if not preview.ok or preview.data is None:
            return False
        explanation = str(preview.data["summary"])
        self._event(events, TraceRole.ASSISTANT, "confirmation_request", explanation)
        confirmation = simulator.answer_confirmation(explanation)
        self._event(events, TraceRole.USER, "confirmation", confirmation)
        if not simulator.scenario.accept_confirmation:
            return False
        arguments = {
            **execute_arguments,
            "confirmation_token": preview.data["confirmation_token"],
            "idempotency_key": f"{trace_id}-{execute_tool}",
            version_key: preview.data["expected_version"],
        }
        return (await self._call(gateway, trace_id, events, execute_tool, arguments)).ok

    async def _call(
        self,
        gateway: ReliableToolGateway,
        trace_id: str,
        events: list[TraceEvent],
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        result = await gateway.call(tool_name, arguments, trace_id=trace_id)
        self._event(
            events,
            TraceRole.TOOL,
            "tool_result",
            result.summary,
            tool_name,
            arguments,
            result.model_dump(mode="json"),
        )
        return result

    @staticmethod
    def _event(
        events: list[TraceEvent],
        role: TraceRole,
        kind: str,
        content: str,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        events.append(
            TraceEvent(
                step=len(events),
                role=role,
                kind=kind,
                content=content,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
            )
        )

    @staticmethod
    def _trajectory(
        scenario: ScenarioSpec,
        trace_id: str,
        events: list[TraceEvent],
        claimed_success: bool,
        final_message: str,
        intents: tuple[Intent, ...],
    ) -> Trajectory:
        return Trajectory(
            scenario_id=scenario.scenario_id,
            trace_id=trace_id,
            events=tuple(events),
            claimed_success=claimed_success,
            final_message=final_message,
            detected_intents=intents,
        )
