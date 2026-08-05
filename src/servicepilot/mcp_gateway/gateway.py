"""Bounded, observable and fault-injectable in-process tool gateway."""

import asyncio
from collections.abc import Callable
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from servicepilot.domain.errors import (
    ConfirmationError,
    IdempotencyConflictError,
    NotFoundError,
    PolicyViolationError,
    VersionConflictError,
)
from servicepilot.mcp_gateway.errors import (
    EmptyResultError,
    LostResponseError,
    PartialResultError,
    ToolErrorCode,
    TransientToolError,
)
from servicepilot.mcp_gateway.faults import FaultKind, FaultPlan
from servicepilot.mcp_servers.registry import ServiceRegistry, UnknownToolError


class ToolFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: ToolErrorCode
    message: str
    retryable: bool


class ToolResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    trace_id: str
    tool_name: str
    attempts: int
    duration_ms: float
    data: dict[str, Any] | None = None
    error: ToolFailure | None = None
    summary: str


class ReliableToolGateway:
    """Apply budget, validation, timeout, retry and error classification."""

    def __init__(
        self,
        registry: ServiceRegistry,
        *,
        timeout_seconds: float = 2.0,
        max_retries: int = 2,
        tool_budget: int = 12,
        faults: FaultPlan | None = None,
        backoff: Callable[[float], None] | None = None,
    ) -> None:
        self.registry = registry
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.tool_budget = tool_budget
        self.faults = faults or FaultPlan()
        self.backoff = backoff
        self._trace_calls: dict[str, int] = {}

    async def call(
        self, tool_name: str, arguments: dict[str, Any], *, trace_id: str
    ) -> ToolResult:
        started = perf_counter()
        calls = self._trace_calls.get(trace_id, 0)
        if calls >= self.tool_budget:
            return self._failure(
                trace_id,
                tool_name,
                0,
                started,
                ToolErrorCode.BUDGET_EXCEEDED,
                "tool budget exhausted",
                False,
            )
        self._trace_calls[trace_id] = calls + 1

        for attempt in range(1, self.max_retries + 2):
            try:
                fault = self.faults.next(tool_name)
                if fault is FaultKind.TIMEOUT:
                    raise TimeoutError("injected timeout")
                if fault is FaultKind.TRANSIENT:
                    raise TransientToolError("injected transient failure")
                data = self.registry.call(tool_name, arguments)
                if fault is FaultKind.LOST_RESPONSE:
                    raise LostResponseError("response lost after commit")
                if fault is FaultKind.EMPTY_RESULT:
                    raise EmptyResultError("injected empty result")
                if fault is FaultKind.PARTIAL_RESULT:
                    raise PartialResultError("injected partial result")
                return ToolResult(
                    ok=True,
                    trace_id=trace_id,
                    tool_name=tool_name,
                    attempts=attempt,
                    duration_ms=self._elapsed_ms(started),
                    data=data,
                    summary=self._summary(data),
                )
            except Exception as exc:
                code, retryable = self._classify(exc)
                if retryable and attempt <= self.max_retries:
                    delay = 0.01 * (2 ** (attempt - 1))
                    if self.backoff is not None:
                        self.backoff(delay)
                    else:
                        await asyncio.sleep(delay)
                    continue
                return self._failure(
                    trace_id,
                    tool_name,
                    attempt,
                    started,
                    code,
                    str(exc),
                    retryable,
                )
        raise AssertionError("retry loop must return")

    @staticmethod
    def _classify(exc: Exception) -> tuple[ToolErrorCode, bool]:
        if isinstance(exc, ValidationError):
            return ToolErrorCode.VALIDATION, False
        if isinstance(exc, UnknownToolError):
            return ToolErrorCode.UNKNOWN_TOOL, False
        if isinstance(exc, NotFoundError):
            return ToolErrorCode.NOT_FOUND, False
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return ToolErrorCode.TIMEOUT, True
        if isinstance(exc, TransientToolError):
            return ToolErrorCode.TRANSIENT, True
        if isinstance(exc, EmptyResultError):
            return ToolErrorCode.EMPTY_RESULT, False
        if isinstance(exc, PartialResultError):
            return ToolErrorCode.PARTIAL_RESULT, False
        if isinstance(exc, ConfirmationError):
            return ToolErrorCode.CONFIRMATION_REQUIRED, False
        if isinstance(exc, VersionConflictError):
            return ToolErrorCode.VERSION_CONFLICT, False
        if isinstance(exc, IdempotencyConflictError):
            return ToolErrorCode.IDEMPOTENCY_CONFLICT, False
        if isinstance(exc, PolicyViolationError):
            return ToolErrorCode.POLICY_VIOLATION, False
        return ToolErrorCode.INTERNAL, False

    def _failure(
        self,
        trace_id: str,
        tool_name: str,
        attempts: int,
        started: float,
        code: ToolErrorCode,
        message: str,
        retryable: bool,
    ) -> ToolResult:
        return ToolResult(
            ok=False,
            trace_id=trace_id,
            tool_name=tool_name,
            attempts=attempts,
            duration_ms=self._elapsed_ms(started),
            error=ToolFailure(code=code, message=message, retryable=retryable),
            summary=f"{code}: {message}"[:240],
        )

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((perf_counter() - started) * 1000, 3)

    @staticmethod
    def _summary(data: dict[str, Any]) -> str:
        return repr(data)[:240]
