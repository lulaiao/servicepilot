import hashlib

import pytest

from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.training import (
    DataSplit,
    assign_family_splits,
    build_training_record,
    cross_split_overlap_count,
    deduplicate_records,
    redact_value,
)


def test_redaction_is_recursive_and_counts_sensitive_values() -> None:
    redacted, count = redact_value(
        {
            "email": "call user@example.com or 13812345678",
            "authorization": "Bearer should-not-survive",
            "nested": {"api_key": "secret-value"},
        }
    )

    assert count == 4
    assert redacted["email"] == "call [REDACTED_EMAIL] or [REDACTED_PHONE]"
    assert redacted["authorization"] == "[REDACTED_SECRET]"
    assert redacted["nested"]["api_key"] == "[REDACTED_SECRET]"


def test_family_split_keeps_all_intent_variants_together() -> None:
    scenarios = build_phase3_scenarios()
    assignments = assign_family_splits(scenarios, seed=20260808)

    assert set(assignments.values()) == set(DataSplit)
    for scenario in scenarios:
        expected_hash = hashlib.sha256(f"intent:{scenario.intent.value}".encode()).hexdigest()
        assert expected_hash in assignments


def test_deduplication_and_overlap_audit_use_content_hash() -> None:
    from servicepilot.training.data_models import TrajectoryTrainingRecord

    base = TrajectoryTrainingRecord(
        record_id="record-1",
        source_scenario_id="scenario-1",
        source_trace_id="trace-1",
        scenario_family_sha256="family-1",
        split=DataSplit.TRAIN,
        events=(),
        detected_intents=("order_query",),
        final_message="done",
        task_success=True,
        false_success=False,
        policy_compliant=True,
        content_sha256="content-1",
        redaction_count=0,
    )
    duplicate = base.model_copy(update={"record_id": "record-2", "source_trace_id": "trace-2"})
    leaked = base.model_copy(update={"record_id": "record-3", "split": DataSplit.DEV})

    assert deduplicate_records((base, duplicate)) == (base,)
    assert cross_split_overlap_count((base, leaked), "content_sha256") == 1


@pytest.mark.asyncio
async def test_real_harness_trajectory_converts_to_versioned_record() -> None:
    scenario = build_phase3_scenarios()[0]
    trajectory, judge, _ = await EvaluationHarness().run_scenario(scenario)

    record = build_training_record(scenario, trajectory, judge, split=DataSplit.TRAIN)

    assert record.schema_version == "servicepilot-trajectory-v1"
    assert record.task_success
    assert record.events
    assert record.content_sha256
