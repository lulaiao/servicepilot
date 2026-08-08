"""Read-only adapters from Harness/Judge outputs into redacted observations."""

from servicepilot.eval.models import JudgeResult, Trajectory
from servicepilot.harness.models import HarnessSession
from servicepilot.monitoring.models import MonitorObservation, MonitorScope

HIGH_RISK_WRITES = {
    "cancel_order",
    "create_refund_request",
    "restore_coupon",
    "reschedule_order",
}


def observation_from_run(
    session: HarnessSession, trajectory: Trajectory, judge: JudgeResult
) -> MonitorObservation:
    """Project execution output without exposing raw arguments or repository access."""
    tool_events = tuple(event for event in trajectory.events if event.tool_name)
    error_codes = tuple(
        str(event.result["error"]["code"])
        for event in tool_events
        if event.result
        and isinstance(event.result.get("error"), dict)
        and event.result["error"].get("code")
    )
    high_risk_write_seen = any(event.tool_name in HIGH_RISK_WRITES for event in tool_events)
    confirmation_seen = any(event.kind == "confirmation" for event in trajectory.events)
    return MonitorObservation(
        scenario_id=session.scenario_id,
        available_scopes=frozenset(MonitorScope),
        claimed_success=trajectory.claimed_success,
        final_state_correct=judge.final_state_correct,
        policy_compliant=judge.policy_compliant,
        forbidden_action_seen="FORBIDDEN_ACTION" in judge.failure_reasons,
        missing_evidence="GOLD_EVIDENCE_MISSING" in judge.failure_reasons,
        termination_reason=(
            session.termination_reason.value if session.termination_reason else None
        ),
        retries_used=session.retries_used,
        max_retries=session.config.budgets.max_retries,
        tool_error_codes=error_codes,
        prompt_injection_detected=any(
            event.kind == "guardrail_stop" for event in trajectory.events
        ),
        high_risk_write_seen=high_risk_write_seen,
        confirmation_seen=confirmation_seen,
    )
