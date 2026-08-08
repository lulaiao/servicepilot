"""Deterministic redaction, deduplication, and leakage-resistant splitting."""

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

from servicepilot.eval.models import JudgeResult, ScenarioSpec, Trajectory
from servicepilot.training.data_models import (
    DataSplit,
    TrainingEvent,
    TrajectoryTrainingRecord,
)

GENERATOR_VERSION = "phase8-data-v1"
_SECRET_KEYS = frozenset({"authorization", "api_key", "apikey", "password", "secret", "token"})
_PATTERNS = (
    (re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+"), "[REDACTED_BEARER]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[REDACTED_PHONE]"),
    (
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "[REDACTED_EMAIL]",
    ),
)


def redact_value(value: Any, *, key: str | None = None) -> tuple[Any, int]:
    if key is not None and key.lower() in _SECRET_KEYS:
        return "[REDACTED_SECRET]", 1
    if isinstance(value, str):
        current = value
        count = 0
        for pattern, replacement in _PATTERNS:
            current, replacements = pattern.subn(replacement, current)
            count += replacements
        return current, count
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        count = 0
        for child_key, child_value in value.items():
            output[child_key], child_count = redact_value(child_value, key=str(child_key))
            count += child_count
        return output, count
    if isinstance(value, (list, tuple)):
        sequence_output: list[Any] = []
        count = 0
        for item in value:
            child, child_count = redact_value(item)
            sequence_output.append(child)
            count += child_count
        return sequence_output, count
    return value, 0


def family_hash(scenario: ScenarioSpec) -> str:
    """Group paraphrases and fault variants by business intent family."""
    return hashlib.sha256(f"intent:{scenario.intent.value}".encode()).hexdigest()


def assign_family_splits(scenarios: Iterable[ScenarioSpec], *, seed: int) -> dict[str, DataSplit]:
    families = sorted({family_hash(item) for item in scenarios})
    ordered = sorted(
        families,
        key=lambda item: hashlib.sha256(f"{seed}:{item}".encode()).hexdigest(),
    )
    dev_count = max(1, round(len(ordered) * 0.15))
    sealed_count = max(1, round(len(ordered) * 0.15))
    train_end = len(ordered) - dev_count - sealed_count
    if train_end <= 0:
        raise ValueError("at least three scenario families are required")
    return {
        family: (
            DataSplit.TRAIN
            if index < train_end
            else DataSplit.DEV
            if index < train_end + dev_count
            else DataSplit.SEALED_TEST
        )
        for index, family in enumerate(ordered)
    }


def build_training_record(
    scenario: ScenarioSpec,
    trajectory: Trajectory,
    judge: JudgeResult,
    *,
    split: DataSplit,
) -> TrajectoryTrainingRecord:
    events: list[TrainingEvent] = []
    redaction_count = 0
    for event in trajectory.events:
        payload, count = redact_value(
            {
                "content": event.content,
                "arguments": event.arguments,
                "result": event.result,
            }
        )
        redaction_count += count
        events.append(
            TrainingEvent(
                role=event.role.value,
                kind=event.kind,
                content=payload["content"],
                tool_name=event.tool_name,
                arguments=payload["arguments"],
                result=payload["result"],
            )
        )
    final_message, count = redact_value(trajectory.final_message)
    redaction_count += count
    content_payload = {
        "events": [item.model_dump(mode="json") for item in events],
        "detected_intents": [item.value for item in trajectory.detected_intents],
        "final_message": final_message,
        "outcome": {
            "task_success": judge.task_success,
            "false_success": judge.false_success,
            "policy_compliant": judge.policy_compliant,
        },
    }
    content_sha256 = hashlib.sha256(
        json.dumps(content_payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    return TrajectoryTrainingRecord(
        record_id=f"trajectory-{content_sha256[:20]}",
        source_scenario_id=scenario.scenario_id,
        source_trace_id=trajectory.trace_id,
        scenario_family_sha256=family_hash(scenario),
        split=split,
        events=tuple(events),
        detected_intents=tuple(item.value for item in trajectory.detected_intents),
        final_message=final_message,
        task_success=judge.task_success,
        false_success=judge.false_success,
        policy_compliant=judge.policy_compliant,
        content_sha256=content_sha256,
        redaction_count=redaction_count,
    )


def deduplicate_records(
    records: Iterable[TrajectoryTrainingRecord],
) -> tuple[TrajectoryTrainingRecord, ...]:
    unique: dict[str, TrajectoryTrainingRecord] = {}
    for record in records:
        unique.setdefault(record.content_sha256, record)
    return tuple(sorted(unique.values(), key=lambda item: item.record_id))


def cross_split_overlap_count(records: Iterable[TrajectoryTrainingRecord], attribute: str) -> int:
    owners: dict[str, set[DataSplit]] = {}
    for record in records:
        value = str(getattr(record, attribute))
        owners.setdefault(value, set()).add(record.split)
    return sum(len(splits) > 1 for splits in owners.values())
