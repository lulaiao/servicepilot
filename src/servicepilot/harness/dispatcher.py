"""Checkpointing interception boundary around the reliable tool Gateway."""

import hashlib
import json
from collections.abc import Callable
from typing import Any

from servicepilot.harness.guardrails import GuardrailPipeline
from servicepilot.harness.models import (
    GuardrailStage,
    HarnessTerminationReason,
    ToolStepCheckpoint,
    ToolStepStatus,
)
from servicepilot.mcp_gateway.errors import ToolErrorCode
from servicepilot.mcp_gateway.gateway import ReliableToolGateway, ToolResult


class SimulatedHarnessInterruption(RuntimeError):
    """Test-only interruption raised after a durable tool-result checkpoint."""


class HarnessControlStop(RuntimeError):
    def __init__(
        self, reason: HarnessTerminationReason, message: str
    ) -> None:
        super().__init__(message)
        self.reason = reason


class CheckpointingToolDispatcher:
    def __init__(
        self,
        gateway: ReliableToolGateway,
        *,
        existing_steps: tuple[ToolStepCheckpoint, ...] = (),
        persist: Callable[[ToolStepCheckpoint], None],
        interrupt_after_committed_tool: str | None = None,
        guardrails: GuardrailPipeline | None = None,
        max_tool_calls: int = 12,
        max_retries: int = 2,
    ) -> None:
        self.gateway = gateway
        self.persist = persist
        self.interrupt_after_committed_tool = interrupt_after_committed_tool
        self._interrupted = False
        self.guardrails = guardrails or GuardrailPipeline()
        self.max_tool_calls = max_tool_calls
        self.max_retries = max_retries
        self.tool_calls_used = 0
        self.retries_used = 0
        self._ordinals: dict[str, int] = {}
        self._committed = {
            step.call_key: step
            for step in existing_steps
            if step.status is ToolStepStatus.COMMITTED
        }

    async def call(
        self, tool_name: str, arguments: dict[str, Any], *, trace_id: str
    ) -> ToolResult:
        arguments_sha = hashlib.sha256(
            json.dumps(arguments, sort_keys=True, default=str).encode()
        ).hexdigest()
        base = f"{tool_name}:{arguments_sha}"
        ordinal = self._ordinals.get(base, 0)
        self._ordinals[base] = ordinal + 1
        call_key = f"{base}:{ordinal}"
        cached = self._committed.get(call_key)
        if cached is not None and cached.result is not None:
            return ToolResult.model_validate(cached.result)

        sequence = len(self._committed) + ordinal
        if self.tool_calls_used >= self.max_tool_calls:
            self._persist_blocked(
                sequence, call_key, tool_name, arguments_sha, ()
            )
            raise HarnessControlStop(
                HarnessTerminationReason.TOOL_BUDGET_EXHAUSTED,
                "Harness tool-call budget exhausted",
            )
        decisions = self.guardrails.evaluate(
            GuardrailStage.TOOL,
            {"tool_name": tool_name, "arguments": arguments},
        )
        if not self.guardrails.allowed(decisions):
            self._persist_blocked(
                sequence,
                call_key,
                tool_name,
                arguments_sha,
                tuple(item.model_dump(mode="json") for item in decisions),
            )
            raise HarnessControlStop(
                HarnessTerminationReason.GUARDRAIL_STOP,
                "TOOL-stage guardrail rejected dispatch",
            )
        self.tool_calls_used += 1
        self.persist(
            ToolStepCheckpoint(
                sequence=sequence,
                call_key=call_key,
                tool_name=tool_name,
                arguments_sha256=arguments_sha,
                status=ToolStepStatus.STARTED,
                guardrail_decisions=tuple(
                    item.model_dump(mode="json") for item in decisions
                ),
            )
        )
        result = await self.gateway.call(tool_name, arguments, trace_id=trace_id)
        self.retries_used += max(0, result.attempts - 1)
        committed = ToolStepCheckpoint(
            sequence=sequence,
            call_key=call_key,
            tool_name=tool_name,
            arguments_sha256=arguments_sha,
            status=ToolStepStatus.COMMITTED,
            result=result.model_dump(mode="json"),
            guardrail_decisions=tuple(
                item.model_dump(mode="json") for item in decisions
            ),
        )
        self._committed[call_key] = committed
        self.persist(committed)
        if not result.ok and result.error is not None:
            recovery_reason = {
                ToolErrorCode.CONFIRMATION_REQUIRED: (
                    HarnessTerminationReason.CONFIRMATION_RECOVERY_REQUIRED
                ),
                ToolErrorCode.VERSION_CONFLICT: (
                    HarnessTerminationReason.VERSION_CONFLICT_RECOVERY_REQUIRED
                ),
            }.get(result.error.code)
            if recovery_reason is not None:
                raise HarnessControlStop(
                    recovery_reason,
                    f"recovery required after {result.error.code.value}",
                )
        if (
            not result.ok
            and result.error is not None
            and result.error.retryable
            and result.attempts >= self.max_retries + 1
        ):
            raise HarnessControlStop(
                HarnessTerminationReason.RETRY_BUDGET_EXHAUSTED,
                "Harness retry budget exhausted",
            )
        if (
            tool_name == self.interrupt_after_committed_tool
            and not self._interrupted
        ):
            self._interrupted = True
            raise SimulatedHarnessInterruption(
                f"interrupted after checkpointing {tool_name} result"
            )
        return result

    def _persist_blocked(
        self,
        sequence: int,
        call_key: str,
        tool_name: str,
        arguments_sha: str,
        decisions: tuple[dict[str, Any], ...],
    ) -> None:
        self.persist(
            ToolStepCheckpoint(
                sequence=sequence,
                call_key=call_key,
                tool_name=tool_name,
                arguments_sha256=arguments_sha,
                status=ToolStepStatus.BLOCKED,
                guardrail_decisions=decisions,
            )
        )
