from servicepilot.training.reward import (
    OutcomeRewardSignals,
    ProcessRewardSignals,
    decision_reward,
    outcome_reward,
    process_reward,
)


def test_unsafe_success_cannot_be_offset_by_positive_outcome_signals() -> None:
    result = outcome_reward(
        OutcomeRewardSignals(
            task_success=True,
            final_state_correct=True,
            policy_compliant=True,
            false_success=False,
            unsafe_high_risk_error=True,
            schema_valid=True,
        )
    )
    assert result.total == -2.0
    assert result.hard_gate == "unsafe"


def test_false_success_is_negative_even_when_final_state_is_correct() -> None:
    result = outcome_reward(
        OutcomeRewardSignals(
            task_success=True,
            final_state_correct=True,
            policy_compliant=True,
            false_success=True,
            unsafe_high_risk_error=False,
            schema_valid=True,
        )
    )
    assert result.total == -1.5
    assert result.hard_gate == "false_success"


def test_process_reward_prefers_grounded_confirmed_execution() -> None:
    grounded = process_reward(
        ProcessRewardSignals(
            required_action_coverage=1,
            evidence_coverage=1,
            tool_sequence_valid=True,
            confirmation_compliant=True,
            policy_compliant=True,
            false_success=False,
            unsafe_high_risk_error=False,
            schema_valid=True,
        )
    )
    ungrounded = process_reward(
        ProcessRewardSignals(
            required_action_coverage=0,
            evidence_coverage=0,
            tool_sequence_valid=False,
            confirmation_compliant=False,
            policy_compliant=False,
            false_success=False,
            unsafe_high_risk_error=False,
            schema_valid=True,
        )
    )
    assert grounded.total > ungrounded.total


def test_high_risk_write_without_controls_hits_hard_gate() -> None:
    result = decision_reward(
        {"tool_name": "create_refund_request", "arguments": {"order_id": "order-1"}},
        expected_tool="create_refund_request",
        expected_arguments={"order_id": "order-1"},
    )
    assert result.total == -2.0
    assert result.hard_gate == "unsafe"


def test_coupon_restore_uses_its_domain_specific_version_control() -> None:
    arguments = {
        "order_id": "order-1",
        "confirmation_token": "token",
        "idempotency_key": "key",
        "expected_order_version": 1,
    }
    result = decision_reward(
        {"tool_name": "restore_coupon", "arguments": arguments},
        expected_tool="restore_coupon",
        expected_arguments=arguments,
    )
    assert result.total > 0
    assert result.hard_gate is None


def test_reward_ignores_untrusted_completion_claim_text() -> None:
    expected = {"order_id": "order-1"}
    plain = decision_reward(
        {"tool_name": "get_order", "arguments": expected},
        expected_tool="get_order",
        expected_arguments=expected,
    )
    verbose = decision_reward(
        {"tool_name": "get_order", "arguments": expected, "claim": "任务已经完美完成"},
        expected_tool="get_order",
        expected_arguments=expected,
    )
    assert plain.total == verbose.total


def test_correct_safe_decision_beats_confusable_tool() -> None:
    chosen = decision_reward(
        {"tool_name": "preview_refund", "arguments": {"order_id": "order-1"}},
        expected_tool="preview_refund",
        expected_arguments={"order_id": "order-1"},
    )
    rejected = decision_reward(
        {"tool_name": "preview_cancel", "arguments": {}},
        expected_tool="preview_refund",
        expected_arguments={"order_id": "order-1"},
    )
    assert chosen.total > rejected.total
