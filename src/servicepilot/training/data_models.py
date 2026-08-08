"""Versioned contracts for privacy-safe trajectory datasets."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class DataSplit(StrEnum):
    TRAIN = "train"
    DEV = "dev"
    SEALED_TEST = "sealed_test"


class TrainingEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str
    kind: str
    content: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


class TrajectoryTrainingRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "servicepilot-trajectory-v1"
    record_id: str
    source_scenario_id: str
    source_trace_id: str
    scenario_family_sha256: str
    split: DataSplit
    events: tuple[TrainingEvent, ...]
    detected_intents: tuple[str, ...]
    final_message: str
    task_success: bool
    false_success: bool
    policy_compliant: bool
    content_sha256: str
    redaction_count: int


class TrajectoryDatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str
    generator_version: str
    code_revision: str
    seed: int
    source_scenario_sha256: str
    output_sha256: str
    raw_record_count: int
    deduplicated_record_count: int
    duplicate_count: int
    redaction_count: int
    split_counts: dict[DataSplit, int]
    split_family_counts: dict[DataSplit, int]
    cross_split_family_overlap_count: int
    cross_split_content_overlap_count: int
