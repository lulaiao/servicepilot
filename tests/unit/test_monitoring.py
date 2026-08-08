import pytest

from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.monitoring import (
    PHASE7_FAULT_PROFILES,
    AsyncMonitor,
    DeterministicMonitor,
    MonitorFaultClass,
    MonitorObservation,
    MonitorPermissionError,
    MonitorScope,
    inject_monitor_faults,
    observation_from_run,
)

ALL_SCOPES = frozenset(MonitorScope)


def observation(**updates: object) -> MonitorObservation:
    return MonitorObservation(
        scenario_id="monitor-case",
        available_scopes=ALL_SCOPES,
    ).model_copy(update=updates)


@pytest.mark.parametrize(
    ("updates", "expected"),
    (
        ({"claimed_success": True, "final_state_correct": False}, MonitorFaultClass.FALSE_SUCCESS),
        ({"policy_compliant": False}, MonitorFaultClass.POLICY_VIOLATION),
        ({"forbidden_action_seen": True}, MonitorFaultClass.FORBIDDEN_ACTION),
        ({"missing_evidence": True}, MonitorFaultClass.MISSING_EVIDENCE),
        ({"termination_reason": "tool_budget_exhausted"}, MonitorFaultClass.BUDGET_EXHAUSTION),
        ({"retries_used": 3, "max_retries": 2}, MonitorFaultClass.RETRY_STORM),
        ({"tool_error_codes": ("TIMEOUT",)}, MonitorFaultClass.TOOL_FAILURE),
        ({"write_operation_ids": ("write-1", "write-1")}, MonitorFaultClass.DUPLICATE_WRITE),
        (
            {"committed_response_lost": True, "recovery_idempotent": False},
            MonitorFaultClass.UNSAFE_LOST_RESPONSE_RECOVERY,
        ),
        ({"version_conflict_count": 1}, MonitorFaultClass.VERSION_CONFLICT),
        ({"prompt_injection_detected": True}, MonitorFaultClass.PROMPT_INJECTION),
        ({"memory_conflict_unresolved": True}, MonitorFaultClass.MEMORY_CONFLICT),
        (
            {"high_risk_write_seen": True, "confirmation_seen": False},
            MonitorFaultClass.UNCONFIRMED_HIGH_RISK_WRITE,
        ),
    ),
)
def test_monitor_detects_each_fault_class(
    updates: dict[str, object], expected: MonitorFaultClass
) -> None:
    report = DeterministicMonitor().evaluate(observation(**updates))

    assert expected in {item.fault_class for item in report.findings}
    assert report.evaluated_rule_count == 13


def test_monitor_has_no_false_positive_on_clean_observation() -> None:
    report = DeterministicMonitor().evaluate(observation())

    assert report.findings == ()


def test_monitor_rejects_observation_without_least_privilege_scopes() -> None:
    restricted = observation(available_scopes=frozenset({MonitorScope.TRACE_SUMMARY}))

    with pytest.raises(MonitorPermissionError, match="missing monitor scopes"):
        DeterministicMonitor().evaluate(restricted)


@pytest.mark.asyncio
async def test_async_monitor_processes_bounded_queue_without_changing_rules() -> None:
    monitor = AsyncMonitor(max_queue_size=1)
    current = observation(prompt_injection_detected=True)

    await monitor.submit(current)
    report = await monitor.process_one()

    assert report.findings[0].fault_class is MonitorFaultClass.PROMPT_INJECTION
    assert monitor.queue.empty()


@pytest.mark.asyncio
async def test_real_harness_run_is_projected_without_repository_access() -> None:
    harness = EvaluationHarness()
    trajectory, judge, _ = await harness.run_scenario(build_phase3_scenarios()[0])
    session = next(iter(harness.sessions.values()))

    current = observation_from_run(session, trajectory, judge)
    report = DeterministicMonitor().evaluate(current)

    assert current.scenario_id == session.scenario_id
    assert current.available_scopes == ALL_SCOPES
    assert report.findings == ()


def test_phase7_workload_profiles_cover_clean_single_and_mixed_faults() -> None:
    assert len(PHASE7_FAULT_PROFILES) == 28
    assert any(not profile for profile in PHASE7_FAULT_PROFILES)
    assert {next(iter(profile)) for profile in PHASE7_FAULT_PROFILES if len(profile) == 1} == set(
        MonitorFaultClass
    )
    assert any(len(profile) > 1 for profile in PHASE7_FAULT_PROFILES)

    for profile in PHASE7_FAULT_PROFILES:
        current = inject_monitor_faults(observation(), profile)
        predicted = {item.fault_class for item in DeterministicMonitor().evaluate(current).findings}
        assert predicted == set(profile)
