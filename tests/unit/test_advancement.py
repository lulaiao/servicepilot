from servicepilot.training.advancement import AgentMetricSnapshot, assess_grpo_advancement


def snapshot(**updates: float | int) -> AgentMetricSnapshot:
    return AgentMetricSnapshot(
        task_success=0.9,
        final_state_accuracy=0.9,
        policy_violation_rate=0,
        false_success_rate=0,
        unsafe_high_risk_error_rate=0,
        schema_valid_rate=1,
        runtime_error_count=0,
    ).model_copy(update=updates)


def test_advancement_requires_strict_utility_gain() -> None:
    decision = assess_grpo_advancement(snapshot(), snapshot())
    assert not decision.allowed
    assert "strict_task_success_gain" in decision.failed_gates


def test_schema_regression_blocks_otherwise_improved_candidate() -> None:
    decision = assess_grpo_advancement(
        snapshot(), snapshot(task_success=0.95, schema_valid_rate=0.97)
    )
    assert not decision.allowed
    assert "schema_not_regressed" in decision.failed_gates


def test_safe_utility_improvement_is_allowed() -> None:
    decision = assess_grpo_advancement(snapshot(), snapshot(task_success=0.95))
    assert decision.allowed
