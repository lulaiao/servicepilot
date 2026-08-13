"""Deterministic per-tool fault injection plans."""

from collections import deque
from enum import StrEnum
from threading import RLock


class FaultKind(StrEnum):
    TIMEOUT = "TIMEOUT"
    TRANSIENT = "TRANSIENT"
    EMPTY_RESULT = "EMPTY_RESULT"
    PARTIAL_RESULT = "PARTIAL_RESULT"
    LOST_RESPONSE = "LOST_RESPONSE"


class FaultPlan:
    """Consume configured faults in call order, then return normal behavior."""

    def __init__(self, faults: dict[str, list[FaultKind]] | None = None) -> None:
        self._lock = RLock()
        self._faults = {tool: deque(tool_faults) for tool, tool_faults in (faults or {}).items()}

    def next(self, tool_name: str) -> FaultKind | None:
        with self._lock:
            queue = self._faults.get(tool_name)
            if not queue:
                return None
            return queue.popleft()
