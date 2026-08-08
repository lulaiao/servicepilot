"""Least-privilege contracts for synchronous and asynchronous monitors."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MonitorScope(StrEnum):
    TRACE_SUMMARY = "trace_summary"
    JUDGE_RESULT = "judge_result"
    HARNESS_BUDGETS = "harness_budgets"


class MonitorFaultClass(StrEnum):
    FALSE_SUCCESS = "false_success"
    POLICY_VIOLATION = "policy_violation"
    FORBIDDEN_ACTION = "forbidden_action"
    MISSING_EVIDENCE = "missing_evidence"
    BUDGET_EXHAUSTION = "budget_exhaustion"
    RETRY_STORM = "retry_storm"
    TOOL_FAILURE = "tool_failure"
    DUPLICATE_WRITE = "duplicate_write"
    UNSAFE_LOST_RESPONSE_RECOVERY = "unsafe_lost_response_recovery"
    VERSION_CONFLICT = "version_conflict"
    PROMPT_INJECTION = "prompt_injection"
    MEMORY_CONFLICT = "memory_conflict"
    UNCONFIRMED_HIGH_RISK_WRITE = "unconfirmed_high_risk_write"


class MonitorSeverity(StrEnum):
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class MonitorRecommendation(StrEnum):
    ALERT = "alert"
    BLOCK = "block_recommendation"
    HANDOFF = "handoff_recommendation"


class MonitorObservation(BaseModel):
    """Redacted monitor input; deliberately excludes repository and raw arguments."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    available_scopes: frozenset[MonitorScope]
    claimed_success: bool = False
    final_state_correct: bool = True
    policy_compliant: bool = True
    forbidden_action_seen: bool = False
    missing_evidence: bool = False
    termination_reason: str | None = None
    retries_used: int = Field(default=0, ge=0)
    max_retries: int = Field(default=2, ge=0)
    tool_error_codes: tuple[str, ...] = ()
    write_operation_ids: tuple[str, ...] = ()
    committed_response_lost: bool = False
    recovery_idempotent: bool = True
    version_conflict_count: int = Field(default=0, ge=0)
    prompt_injection_detected: bool = False
    memory_conflict_unresolved: bool = False
    high_risk_write_seen: bool = False
    confirmation_seen: bool = True


class MonitorFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    fault_class: MonitorFaultClass
    severity: MonitorSeverity
    recommendation: MonitorRecommendation
    reason: str


class MonitorReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    findings: tuple[MonitorFinding, ...]
    evaluated_rule_count: int
    monitor_version: str


class MonitorPermissionError(PermissionError):
    """Raised when a monitor input omits an explicitly required read scope."""
