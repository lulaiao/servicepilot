"""Frozen scenario, trace and deterministic evaluation schemas."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from servicepilot.domain.models import CouponStatus, OrderStatus
from servicepilot.mcp_gateway.faults import FaultKind


class Intent(StrEnum):
    ORDER_QUERY = "order_query"
    CANCEL_ORDER = "cancel_order"
    FULL_REFUND = "full_refund"
    PARTIAL_REFUND = "partial_refund"
    DELIVERY_DELAY = "delivery_delay"
    MISSING_OR_WRONG_ITEM = "missing_or_wrong_item"
    DUPLICATE_CHARGE = "duplicate_charge"
    COUPON_ISSUE = "coupon_issue"
    RESCHEDULE = "reschedule"
    COMPLAINT_ESCALATION = "complaint_escalation"
    MULTI_INTENT = "multi_intent"
    OUT_OF_SCOPE = "out_of_scope"


class ExpectedFinalState(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_status: OrderStatus | None = None
    refund_amount: Decimal | None = None
    coupon_status: CouponStatus | None = None
    delivery_issue_count: int = 0
    handoff_ticket_count: int = 0
    scheduled_at: datetime | None = None
    write_expected: bool = False


class ScenarioSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    intent: Intent
    user_utterance: str
    order_id: str
    user_id: str
    initial_order_status: OrderStatus
    requested_amount: Decimal | None = None
    reason: str | None = None
    new_time: datetime | None = None
    reveal_order_id_on_question: bool = True
    accept_confirmation: bool = True
    allowed_actions: tuple[str, ...]
    forbidden_actions: tuple[str, ...] = ()
    gold_evidence_ids: tuple[str, ...] = ()
    faults: dict[str, tuple[FaultKind, ...]] = Field(default_factory=dict)
    expected: ExpectedFinalState


class TraceRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    JUDGE = "judge"


class TraceEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    step: int
    role: TraceRole
    kind: str
    content: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


class Trajectory(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    trace_id: str
    events: tuple[TraceEvent, ...]
    claimed_success: bool
    final_message: str
    detected_intents: tuple[Intent, ...]


class JudgeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    task_success: bool
    final_state_correct: bool
    policy_compliant: bool
    false_success: bool
    tool_sequence_valid: bool
    failure_reasons: tuple[str, ...]
    turns: int
    tool_calls: int


class EvalReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_count: int
    task_success_count: int
    executable_task_success_rate: float
    final_state_accuracy: float
    policy_violation_rate: float
    false_success_rate: float
    average_turns: float
    average_tool_calls: float
    by_intent: dict[str, dict[str, float | int]]
    failures: tuple[JudgeResult, ...]
