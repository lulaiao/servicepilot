"""Checkpoint adapters for Harness sessions."""

from threading import RLock

from servicepilot.harness.models import HarnessSession


class InMemoryCheckpointStore:
    def __init__(self) -> None:
        self._sessions: dict[str, HarnessSession] = {}
        self._lock = RLock()

    def save(self, session: HarnessSession) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def load(self, session_id: str) -> HarnessSession | None:
        with self._lock:
            return self._sessions.get(session_id)
