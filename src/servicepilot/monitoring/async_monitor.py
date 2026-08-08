"""Bounded asynchronous adapter around the deterministic Monitor."""

import asyncio

from servicepilot.monitoring.deterministic import DeterministicMonitor
from servicepilot.monitoring.models import MonitorObservation, MonitorReport


class AsyncMonitor:
    def __init__(
        self, monitor: DeterministicMonitor | None = None, *, max_queue_size: int = 128
    ) -> None:
        if max_queue_size <= 0:
            raise ValueError("max_queue_size must be positive")
        self.monitor = monitor or DeterministicMonitor()
        self.queue: asyncio.Queue[MonitorObservation] = asyncio.Queue(maxsize=max_queue_size)

    async def submit(self, observation: MonitorObservation) -> None:
        """Apply bounded backpressure instead of dropping safety observations."""
        await self.queue.put(observation)

    async def process_one(self) -> MonitorReport:
        observation = await self.queue.get()
        try:
            return self.monitor.evaluate(observation)
        finally:
            self.queue.task_done()
