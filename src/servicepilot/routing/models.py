"""Typed intent extraction and stateful routing contracts."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from servicepilot.eval.models import Intent
from servicepilot.mcp_gateway.errors import ToolErrorCode


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentRole(StrEnum):
    COORDINATOR = "coordinator"
    ORDER = "order_agent"
    AFTER_SALES = "after_sales_agent"
    POLICY = "policy_agent"
    ESCALATION = "escalation_agent"
    VERIFIER = "verifier"


class IntentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    primary_intent: Intent
    secondary_intents: tuple[Intent, ...] = ()
    slots: dict[str, str | None] = Field(default_factory=dict)
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    needs_clarification: bool
    injection_detected: bool = False


class ToolObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: str
    ok: bool
    error_code: ToolErrorCode | None = None


class DialogueState(BaseModel):
    model_config = ConfigDict(frozen=True)

    turn: int = 0
    intent: IntentResult
    confirmed_slots: dict[str, str] = Field(default_factory=dict)
    completed_tools: tuple[str, ...] = ()
    failed_tools: tuple[ToolObservation, ...] = ()
    order_status: str | None = None
    pending_action: str | None = None
    tool_budget_remaining: int = 12
    retry_budget_remaining: int = 2
    monitor_alerts: tuple[str, ...] = ()


class RouteDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: AgentRole
    reason: str
    should_clarify: bool = False
    should_stop: bool = False
