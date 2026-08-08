"""Typed contracts for the Agent runtime and evaluation Harnesses."""

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from servicepilot.eval.models import Trajectory


class HarnessSessionStatus(StrEnum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLAYED = "replayed"
    INTERRUPTED = "interrupted"


class HarnessTerminationReason(StrEnum):
    COMPLETED = "completed"
    GUARDRAIL_STOP = "guardrail_stop"
    BUDGET_EXHAUSTED = "budget_exhausted"
    RUNTIME_ERROR = "runtime_error"
    REPLAY_COMPLETED = "replay_completed"
    INTERRUPTED = "interrupted"


class ReplayMode(StrEnum):
    VERIFY_ONLY = "verify_only"


class GuardrailStage(StrEnum):
    INPUT = "input"
    TOOL = "tool"
    OUTPUT = "output"


class HarnessBudgets(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_turns: int = Field(default=24, gt=0)
    max_tool_calls: int = Field(default=12, gt=0)
    max_retries: int = Field(default=2, ge=0)
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_model_tokens: int | None = Field(default=None, gt=0)


class HarnessRunConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    code_revision: str
    scenario_sha256: str
    model_revision: str = "deterministic-rule"
    prompt_revision: str = "phase4-rule-v1"
    seed: int = 20260805
    decoding: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )
    budgets: HarnessBudgets = Field(default_factory=HarnessBudgets)

    def fingerprint(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class HarnessEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    payload_sha256: str

    @classmethod
    def create(
        cls, sequence: int, kind: str, payload: dict[str, Any]
    ) -> "HarnessEvent":
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, default=str
        ).encode()
        return cls(
            sequence=sequence,
            kind=kind,
            payload=payload,
            payload_sha256=hashlib.sha256(encoded).hexdigest(),
        )


class HarnessSession(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    scenario_id: str
    config: HarnessRunConfig
    status: HarnessSessionStatus = HarnessSessionStatus.INITIALIZED
    termination_reason: HarnessTerminationReason | None = None
    events: tuple[HarnessEvent, ...] = ()
    trajectory: Trajectory | None = None
    error: str | None = None
    tool_steps: tuple["ToolStepCheckpoint", ...] = ()


class ToolStepStatus(StrEnum):
    STARTED = "started"
    COMMITTED = "committed"


class ToolStepCheckpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    sequence: int
    call_key: str
    tool_name: str
    arguments_sha256: str
    status: ToolStepStatus
    result: dict[str, Any] | None = None


class GuardrailDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    guardrail: str
    reason: str
