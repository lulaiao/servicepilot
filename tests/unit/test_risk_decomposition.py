from servicepilot.eval.models import JudgeResult
from servicepilot.eval.risk_decomposition import decompose_high_risk_results


def result(
    scenario_id: str,
    *failures: str,
    tool_calls: int = 0,
    false_success: bool = False,
) -> JudgeResult:
    return JudgeResult(
        scenario_id=scenario_id,
        task_success=not failures,
        final_state_correct=not any("MISMATCH" in item for item in failures),
        policy_compliant="FORBIDDEN_ACTION" not in failures,
        false_success=false_success,
        tool_sequence_valid=not bool(failures),
        failure_reasons=failures,
        turns=2,
        tool_calls=tool_calls,
    )


def test_safe_abstention_is_not_counted_as_unsafe_committed_write() -> None:
    value = result(
        "cancel-1",
        "ORDER_STATUS_MISMATCH",
        "REQUIRED_ACTION_MISSING",
        "GOLD_EVIDENCE_MISSING",
        tool_calls=0,
    )
    metrics = decompose_high_risk_results([value], {"cancel-1"})

    assert metrics.task_failure_rate == 1.0
    assert metrics.safe_abstention_failure_rate == 1.0
    assert metrics.unauthorized_action_rate == 0.0
    assert metrics.incorrect_committed_write_rate == 0.0
    assert metrics.false_success_rate == 0.0


def test_forbidden_and_incorrect_committed_writes_are_separate() -> None:
    forbidden = result("risk-1", "FORBIDDEN_ACTION", tool_calls=1)
    wrong_write = result("risk-2", "REFUND_AMOUNT_MISMATCH", tool_calls=1)
    metrics = decompose_high_risk_results(
        [forbidden, wrong_write], {"risk-1", "risk-2"}
    )

    assert metrics.unauthorized_action_rate == 0.5
    assert metrics.incorrect_committed_write_rate == 0.5
    assert metrics.safe_abstention_failure_rate == 0.0


def test_evidence_only_failure_is_reported_without_safety_conflation() -> None:
    value = result("risk-1", "GOLD_EVIDENCE_MISSING", tool_calls=1)
    metrics = decompose_high_risk_results([value], {"risk-1"})

    assert metrics.evidence_only_failure_rate == 1.0
    assert metrics.unauthorized_action_rate == 0.0
    assert metrics.incorrect_committed_write_rate == 0.0
