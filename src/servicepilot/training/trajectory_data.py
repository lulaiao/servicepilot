"""Deterministic redaction, deduplication, and leakage-resistant splitting."""

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

from servicepilot.eval.models import JudgeResult, ScenarioSpec, Trajectory
from servicepilot.training.data_models import (
    DataSplit,
    PreferenceTrainingRecord,
    SFTTrainingRecord,
    TrainingEvent,
    TrajectoryTrainingRecord,
)

GENERATOR_VERSION = "phase8-data-v1"
_SECRET_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "confirmation_token",
        "idempotency_key",
        "password",
        "secret",
        "token",
    }
)
_PATTERNS = (
    (re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+"), "[REDACTED_BEARER]"),
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[REDACTED_PHONE]"),
    (
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        "[REDACTED_EMAIL]",
    ),
)
_CONFUSABLE_TOOLS: dict[str, tuple[str, ...]] = {
    "get_order": ("create_handoff_ticket", "report_delivery_issue"),
    "preview_cancel": ("preview_refund", "preview_reschedule"),
    "cancel_order": ("create_refund_request", "reschedule_order"),
    "preview_refund": ("preview_cancel", "preview_coupon_restore"),
    "create_refund_request": ("cancel_order", "restore_coupon"),
    "report_delivery_issue": ("create_handoff_ticket", "get_order"),
    "create_handoff_ticket": ("report_delivery_issue", "get_order"),
    "preview_coupon_restore": ("preview_refund", "preview_cancel"),
    "restore_coupon": ("cancel_order", "create_refund_request"),
    "preview_reschedule": ("preview_cancel", "preview_refund"),
    "reschedule_order": ("cancel_order", "create_refund_request"),
}


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


def to_sft_record(record: TrajectoryTrainingRecord) -> SFTTrainingRecord:
    messages = tuple(
        {
            "role": event.role,
            "content": json.dumps(
                {
                    "kind": event.kind,
                    "content": event.content,
                    "tool_name": event.tool_name,
                    "arguments": event.arguments,
                    "result": event.result,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        }
        for event in record.events
    ) + ({"role": "assistant", "content": record.final_message},)
    return SFTTrainingRecord(
        record_id=f"sft-{record.content_sha256[:20]}",
        source_record_id=record.record_id,
        split=record.split,
        messages=messages,
    )


def mine_hard_negatives(
    record: TrajectoryTrainingRecord,
) -> tuple[PreferenceTrainingRecord, ...]:
    """Pair true decisions with confusable tools absent from the gold trajectory."""
    gold_tools = {event.tool_name for event in record.events if event.tool_name}
    preferences: list[PreferenceTrainingRecord] = []
    context: list[dict[str, str]] = []
    for index, event in enumerate(record.events):
        if event.tool_name and event.tool_name in _CONFUSABLE_TOOLS:
            rejected_tool = next(
                (
                    candidate
                    for candidate in _CONFUSABLE_TOOLS[event.tool_name]
                    if candidate not in gold_tools
                ),
                None,
            )
            if rejected_tool is not None:
                digest = hashlib.sha256(
                    f"{record.record_id}:{index}:{event.tool_name}:{rejected_tool}".encode()
                ).hexdigest()
                preferences.append(
                    PreferenceTrainingRecord(
                        record_id=f"preference-{digest[:20]}",
                        source_record_id=record.record_id,
                        split=record.split,
                        decision_index=index,
                        context=tuple(context),
                        chosen={
                            "tool_name": event.tool_name,
                            "arguments": event.arguments or {},
                        },
                        rejected={"tool_name": rejected_tool, "arguments": {}},
                        chosen_tool=event.tool_name,
                        rejected_tool=rejected_tool,
                    )
                )
        context.append({"role": event.role, "content": f"{event.kind}:{event.content}"})
    return tuple(preferences)


def privacy_violation_count(value: Any) -> int:
    """Count raw sensitive values remaining after export."""
    if isinstance(value, str):
        return sum(len(pattern.findall(value)) for pattern, _ in _PATTERNS)
    if isinstance(value, dict):
        violations = 0
        for key, child in value.items():
            if key.lower().endswith("sha256"):
                continue
            if (
                key.lower() in {"record_id", "source_record_id"}
                and isinstance(child, str)
                and re.fullmatch(r"(?:trajectory|sft|preference)-[0-9a-f]{20}", child)
            ):
                continue
            if key.lower() in _SECRET_KEYS and child != "[REDACTED_SECRET]":
                violations += 1
            violations += privacy_violation_count(child)
        return violations
    if isinstance(value, (list, tuple)):
        return sum(privacy_violation_count(item) for item in value)
    return 0


def _character_shingles(text: str, size: int = 5) -> set[str]:
    normalized = "".join(text.lower().split())
    if len(normalized) <= size:
        return {normalized}
    return {normalized[index : index + size] for index in range(len(normalized) - size + 1)}


def near_duplicate_pairs(
    records: Iterable[TrajectoryTrainingRecord], *, threshold: float = 0.9
) -> tuple[tuple[str, str, float], ...]:
    """Audit cross-split near duplicates using deterministic character shingles."""
    items = tuple(records)
    representations = {
        item.record_id: _character_shingles(
            json.dumps(
                {
                    "intents": item.detected_intents,
                    "events": [
                        (event.kind, event.tool_name, event.content) for event in item.events
                    ],
                    "final": item.final_message,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        for item in items
    }
    pairs: list[tuple[str, str, float]] = []
    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            if left.split is right.split:
                continue
            left_set = representations[left.record_id]
            right_set = representations[right.record_id]
            union = left_set | right_set
            score = len(left_set & right_set) / len(union) if union else 1.0
            if score >= threshold:
                pairs.append((left.record_id, right.record_id, round(score, 4)))
    return tuple(pairs)
