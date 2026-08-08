"""Bounded recent-message memory."""

from collections import deque
from threading import RLock

from servicepilot.memory.models import MemoryMessage


class RecentMessageWindow:
    def __init__(self, capacity: int = 8) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._messages: deque[MemoryMessage] = deque(maxlen=capacity)
        self._lock = RLock()

    def append(self, message: MemoryMessage) -> None:
        with self._lock:
            if self._messages and message.turn < self._messages[-1].turn:
                raise ValueError("message turns must be non-decreasing")
            self._messages.append(message)

    def snapshot(self) -> tuple[MemoryMessage, ...]:
        with self._lock:
            return tuple(self._messages)

    def clear(self) -> None:
        with self._lock:
            self._messages.clear()
