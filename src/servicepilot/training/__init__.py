"""Privacy-safe trajectory data and deferred post-training experiments."""

from servicepilot.training.data_models import (
    DataSplit,
    TrainingEvent,
    TrajectoryDatasetManifest,
    TrajectoryTrainingRecord,
)
from servicepilot.training.trajectory_data import (
    GENERATOR_VERSION,
    assign_family_splits,
    build_training_record,
    cross_split_overlap_count,
    deduplicate_records,
    family_hash,
    redact_value,
)

__all__ = [
    "GENERATOR_VERSION",
    "DataSplit",
    "TrainingEvent",
    "TrajectoryDatasetManifest",
    "TrajectoryTrainingRecord",
    "assign_family_splits",
    "build_training_record",
    "cross_split_overlap_count",
    "deduplicate_records",
    "family_hash",
    "redact_value",
]
