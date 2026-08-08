"""Checkpointing interception boundary around the reliable tool Gateway."""

import hashlib
import json
from collections.abc import Callable
from typing import Any

from servicepilot.harness.models import ToolStepCheckpoint, ToolStepStatus
from servicepilot.mcp_gateway.gateway import ReliableToolGateway, ToolResult


class SimulatedHarnessInterruption(RuntimeError):
    """Test-only interruption raised after a durable tool-result checkpoint."""


class CheckpointingToolDispatcher:
    def __init__(
        self,
        gateway: ReliableToolGateway,
        *,
        existing_steps: tuple[ToolStepCheckpoint, ...] = (),
        persist: Callable[[ToolStepCheckpoint], None],
        interrupt_after_committed_tool: str | None = None,
    ) -> None:
        self.gateway = gateway
        self.persist = persist
        self.interrupt_after_committed_tool = interrupt_after_committed_tool
        self._interrupted = False
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
        self.persist(
            ToolStepCheckpoint(
                sequence=sequence,
                call_key=call_key,
                tool_name=tool_name,
                arguments_sha256=arguments_sha,
                status=ToolStepStatus.STARTED,
            )
        )
        result = await self.gateway.call(tool_name, arguments, trace_id=trace_id)
        committed = ToolStepCheckpoint(
            sequence=sequence,
            call_key=call_key,
            tool_name=tool_name,
            arguments_sha256=arguments_sha,
            status=ToolStepStatus.COMMITTED,
            result=result.model_dump(mode="json"),
        )
        self._committed[call_key] = committed
        self.persist(committed)
        if (
            tool_name == self.interrupt_after_committed_tool
            and not self._interrupted
        ):
            self._interrupted = True
            raise SimulatedHarnessInterruption(
                f"interrupted after checkpointing {tool_name} result"
            )
        return result
