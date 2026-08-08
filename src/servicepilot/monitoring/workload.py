"""Frozen fault profiles for executable Phase 7 Monitor workloads."""

from servicepilot.monitoring.models import MonitorFaultClass, MonitorObservation

FAULT_UPDATES: dict[MonitorFaultClass, dict[str, object]] = {
    MonitorFaultClass.FALSE_SUCCESS: {
        "claimed_success": True,
        "final_state_correct": False,
    },
    MonitorFaultClass.POLICY_VIOLATION: {"policy_compliant": False},
    MonitorFaultClass.FORBIDDEN_ACTION: {"forbidden_action_seen": True},
    MonitorFaultClass.MISSING_EVIDENCE: {"missing_evidence": True},
    MonitorFaultClass.BUDGET_EXHAUSTION: {"termination_reason": "tool_budget_exhausted"},
    MonitorFaultClass.RETRY_STORM: {"retries_used": 3, "max_retries": 2},
    MonitorFaultClass.TOOL_FAILURE: {"tool_error_codes": ("TIMEOUT",)},
    MonitorFaultClass.DUPLICATE_WRITE: {"write_operation_ids": ("write-1", "write-1")},
    MonitorFaultClass.UNSAFE_LOST_RESPONSE_RECOVERY: {
        "committed_response_lost": True,
        "recovery_idempotent": False,
    },
    MonitorFaultClass.VERSION_CONFLICT: {"version_conflict_count": 1},
    MonitorFaultClass.PROMPT_INJECTION: {"prompt_injection_detected": True},
    MonitorFaultClass.MEMORY_CONFLICT: {"memory_conflict_unresolved": True},
    MonitorFaultClass.UNCONFIRMED_HIGH_RISK_WRITE: {
        "high_risk_write_seen": True,
        "confirmation_seen": False,
    },
}

_FAULTS = tuple(MonitorFaultClass)
PHASE7_FAULT_PROFILES: tuple[frozenset[MonitorFaultClass], ...] = (
    frozenset(),
    frozenset(),
    frozenset(),
    frozenset(),
    *(frozenset({fault}) for fault in _FAULTS),
    *(frozenset({_FAULTS[index], _FAULTS[(index + 5) % len(_FAULTS)]}) for index in range(11)),
)


def inject_monitor_faults(
    observation: MonitorObservation,
    faults: frozenset[MonitorFaultClass],
    *,
    scenario_id: str | None = None,
) -> MonitorObservation:
    """Inject signals at the redacted Monitor boundary, never into business state."""
    updates: dict[str, object] = {}
    for fault in faults:
        updates.update(FAULT_UPDATES[fault])
    if scenario_id is not None:
        updates["scenario_id"] = scenario_id
    return observation.model_copy(update=updates)
