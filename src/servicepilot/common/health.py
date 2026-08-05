"""Dependency-free process health check used during repository bootstrap."""

from dataclasses import dataclass
import platform


@dataclass(frozen=True)
class HealthReport:
    service: str
    version: str
    status: str
    python_version: str


def check_health() -> HealthReport:
    """Return a stable health record without touching external services."""
    return HealthReport(
        service="servicepilot",
        version="0.1.0",
        status="ok",
        python_version=platform.python_version(),
    )

