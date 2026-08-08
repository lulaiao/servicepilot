import pytest

from servicepilot.training import CheckpointEvidence, checkpoint_step, select_checkpoint


def evidence(
    step: int, loss: float, success: float | None, risk: float | None
) -> CheckpointEvidence:
    return CheckpointEvidence(
        path=f"checkpoint-{step}",
        step=step,
        dev_loss=loss,
        executable_task_success=success,
        high_risk_error_rate=risk,
    )


def test_selection_applies_safety_then_success_then_loss() -> None:
    selected = select_checkpoint(
        (
            evidence(25, 0.4, 0.95, 0.1),
            evidence(50, 0.6, 0.90, 0.0),
            evidence(75, 0.3, 0.90, 0.0),
            evidence(100, 0.2, 0.85, 0.0),
        )
    )
    assert selected.step == 75


def test_selection_refuses_missing_harness_evidence() -> None:
    with pytest.raises(ValueError, match="executable dev evidence"):
        select_checkpoint((evidence(25, 0.4, None, None),))


def test_selection_refuses_unsafe_population() -> None:
    with pytest.raises(ValueError, match="zero-high-risk"):
        select_checkpoint((evidence(25, 0.4, 1.0, 0.01),))


def test_checkpoint_step_is_strict() -> None:
    assert checkpoint_step("runs/seed/checkpoint-125") == 125
    with pytest.raises(ValueError, match="invalid checkpoint"):
        checkpoint_step("runs/seed/best")
