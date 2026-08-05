"""Executable evaluation harness."""

from servicepilot.eval.catalog import build_phase3_scenarios

__all__ = ["build_phase3_scenarios", "run_scenario", "run_suite"]


def __getattr__(name: str) -> object:
    """Load runner exports lazily to avoid agent/evaluation import cycles."""
    if name in {"run_scenario", "run_suite"}:
        from servicepilot.eval.runner import run_scenario, run_suite

        return {"run_scenario": run_scenario, "run_suite": run_suite}[name]
    raise AttributeError(name)
