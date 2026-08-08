"""Least-privilege deterministic and asynchronous monitoring."""

from servicepilot.monitoring.adapters import observation_from_run
from servicepilot.monitoring.async_monitor import AsyncMonitor
from servicepilot.monitoring.deterministic import DeterministicMonitor
from servicepilot.monitoring.models import (
    MonitorFaultClass,
    MonitorFinding,
    MonitorObservation,
    MonitorPermissionError,
    MonitorRecommendation,
    MonitorReport,
    MonitorScope,
    MonitorSeverity,
)
from servicepilot.monitoring.workload import (
    FAULT_UPDATES,
    PHASE7_FAULT_PROFILES,
    inject_monitor_faults,
)

__all__ = [
    "AsyncMonitor",
    "DeterministicMonitor",
    "MonitorFaultClass",
    "MonitorFinding",
    "MonitorObservation",
    "MonitorPermissionError",
    "MonitorRecommendation",
    "MonitorReport",
    "MonitorScope",
    "MonitorSeverity",
    "observation_from_run",
    "FAULT_UPDATES",
    "PHASE7_FAULT_PROFILES",
    "inject_monitor_faults",
]
