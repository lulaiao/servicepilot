"""Deterministic, safety-capped rewards for bounded Phase 9 GRPO experiments."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_HIGH_RISK_TOOLS = frozenset(
    {"cancel_order", "create_refund_request", "reschedule_order", "restore_coupon"}
)
_WRITE_CONTROL_KEYS = {
    "cancel_order": frozenset({"confirmation_token", "idempotency_key", "expected_version"}),
    "create_refund_request": frozenset(
        {"confirmation_token", "idempotency_key", "expected_version"}
    ),
    "reschedule_order": frozenset(
        {"confirmation_token", "idempotency_key", "expected_version"}
    ),
    "restore_coupon": frozenset(
        {"confirmation_token", "idempotency_key", "expected_order_version"}
    ),
}


class OutcomeRewardSignals(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_success: bool
    final_state_correct: bool
    policy_compliant: bool
    false_success: bool
    unsafe_high_risk_error: bool
    schema_valid: bool


class ProcessRewardSignals(BaseModel):
    model_config = ConfigDict(frozen=True)

    required_action_coverage: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    tool_sequence_valid: bool
    confirmation_compliant: bool
    policy_compliant: bool
    false_success: bool
    unsafe_high_risk_error: bool
    schema_valid: bool


class RewardResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: float
    components: dict[str, float]
    hard_gate: str | None = None


def outcome_reward(signals: OutcomeRewardSignals) -> RewardResult:
    """Score final outcomes while making unsafe success strictly unprofitable."""

    if signals.unsafe_high_risk_error:
        return RewardResult(
            total=-2.0,
            components={"unsafe_high_risk_error": -2.0},
            hard_gate="unsafe",
        )
    if signals.false_success:
        return RewardResult(
            total=-1.5,
            components={"false_success": -1.5},
            hard_gate="false_success",
        )
    if not signals.schema_valid:
        return RewardResult(total=-1.0, components={"schema_invalid": -1.0}, hard_gate="schema")
    components = {
        "task_success": 1.0 if signals.task_success else 0.0,
        "final_state_correct": 0.5 if signals.final_state_correct else 0.0,
        "policy_compliant": 0.25 if signals.policy_compliant else -0.5,
    }
    return RewardResult(total=round(sum(components.values()), 6), components=components)


def process_reward(signals: ProcessRewardSignals) -> RewardResult:
    """Score grounded execution steps with the same fail-closed safety caps."""

    if signals.unsafe_high_risk_error:
        return RewardResult(
            total=-2.0,
            components={"unsafe_high_risk_error": -2.0},
            hard_gate="unsafe",
        )
    if signals.false_success:
        return RewardResult(
            total=-1.5,
            components={"false_success": -1.5},
            hard_gate="false_success",
        )
    if not signals.schema_valid:
        return RewardResult(total=-1.0, components={"schema_invalid": -1.0}, hard_gate="schema")
    components = {
        "required_action_coverage": 0.6 * signals.required_action_coverage,
        "evidence_coverage": 0.2 * signals.evidence_coverage,
        "tool_sequence_valid": 0.3 if signals.tool_sequence_valid else -0.3,
        "confirmation_compliant": 0.3 if signals.confirmation_compliant else -0.6,
        "policy_compliant": 0.35 if signals.policy_compliant else -0.7,
    }
    return RewardResult(total=round(sum(components.values()), 6), components=components)


def decision_reward(
    candidate: dict[str, Any], *, expected_tool: str, expected_arguments: dict[str, Any]
) -> RewardResult:
    """Score one structured tool decision without rewarding verbosity or claims."""

    tool_name = candidate.get("tool_name")
    arguments = candidate.get("arguments")
    if not isinstance(tool_name, str) or not isinstance(arguments, dict):
        return RewardResult(total=-1.0, components={"schema_invalid": -1.0}, hard_gate="schema")
    if tool_name in _HIGH_RISK_TOOLS and not _WRITE_CONTROL_KEYS[tool_name].issubset(arguments):
        return RewardResult(
            total=-2.0,
            components={"uncontrolled_high_risk_write": -2.0},
            hard_gate="unsafe",
        )
    tool_score = 1.0 if tool_name == expected_tool else -1.0
    expected_keys = set(expected_arguments)
    argument_coverage = (
        len(expected_keys.intersection(arguments)) / len(expected_keys) if expected_keys else 1.0
    )
    components = {"tool_match": tool_score, "argument_key_coverage": 0.5 * argument_coverage}
    return RewardResult(total=round(sum(components.values()), 6), components=components)
