"""Run-state and safety-first checkpoint selection for formal SFT experiments."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CheckpointEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    step: int = Field(ge=0)
    dev_loss: float = Field(ge=0)
    executable_task_success: float | None = Field(default=None, ge=0, le=1)
    high_risk_error_rate: float | None = Field(default=None, ge=0, le=1)


class SeedRunState(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol_version: str
    seed: int
    status: Literal["training", "awaiting_harness_eval", "selected", "failed"]
    completed_optimizer_steps: int = Field(ge=0)
    checkpoints: tuple[CheckpointEvidence, ...] = ()
    selected_checkpoint: str | None = None


def select_checkpoint(
    checkpoints: tuple[CheckpointEvidence, ...],
) -> CheckpointEvidence:
    """Select only fully evaluated, safe checkpoints using the frozen ordering."""

    if not checkpoints:
        raise ValueError("at least one checkpoint is required")
    if any(
        item.executable_task_success is None or item.high_risk_error_rate is None
        for item in checkpoints
    ):
        raise ValueError("all checkpoints require executable dev evidence")
    safe = [item for item in checkpoints if item.high_risk_error_rate == 0]
    if not safe:
        raise ValueError("no checkpoint satisfies the zero-high-risk-error gate")

    def selection_key(item: CheckpointEvidence) -> tuple[float, float, int, str]:
        if item.executable_task_success is None:
            raise AssertionError("validated checkpoint is missing task success")
        return (-item.executable_task_success, item.dev_loss, item.step, item.path)

    return min(
        safe,
        key=selection_key,
    )


def checkpoint_step(path: str | Path) -> int:
    name = Path(path).name
    prefix = "checkpoint-"
    if not name.startswith(prefix) or not name[len(prefix) :].isdigit():
        raise ValueError(f"invalid checkpoint directory: {name}")
    return int(name[len(prefix) :])
