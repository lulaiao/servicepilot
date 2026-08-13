"""Structural interfaces owned by the Harness boundary."""

from typing import Any, Protocol

from servicepilot.eval.models import ScenarioSpec, Trajectory
from servicepilot.eval.simulator import FSMUserSimulator
from servicepilot.harness.models import (
    GuardrailDecision,
    GuardrailStage,
    HarnessSession,
)
from servicepilot.mcp_gateway.gateway import ReliableToolGateway, ToolResult
from servicepilot.routing.models import IntentResult


class AgentPolicy(Protocol):
    async def run(
        self,
        scenario: ScenarioSpec,
        simulator: FSMUserSimulator,
        gateway: ReliableToolGateway,
    ) -> Trajectory: ...


class ModelAdapter(Protocol):
    def classify(self, text: str) -> IntentResult: ...


class ToolDispatcher(Protocol):
    async def call(
        self, tool_name: str, arguments: dict[str, Any], *, trace_id: str
    ) -> ToolResult: ...


class Guardrail(Protocol):
    name: str

    def evaluate(self, stage: GuardrailStage, payload: dict[str, Any]) -> GuardrailDecision: ...


class CheckpointStore(Protocol):
    def save(self, session: HarnessSession) -> None: ...

    def load(self, session_id: str) -> HarnessSession | None: ...
