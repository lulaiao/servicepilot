"""Durable manifests for isolated and resumable evaluation trials."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.models import JudgeResult, Trajectory


class EvaluationTrialStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class EvaluationTrialRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    scenario_sha256: str
    status: EvaluationTrialStatus
    attempts: int
    trajectory: Trajectory | None = None
    judge_result: JudgeResult | None = None
    error: str | None = None


class EvaluationRunManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    manifest_id: str
    code_revision: str
    config_fingerprint: str
    scenario_set_sha256: str
    max_concurrency: int
    records: tuple[EvaluationTrialRecord, ...] = ()

    @property
    def completed_count(self) -> int:
        return sum(
            item.status is EvaluationTrialStatus.COMPLETED
            for item in self.records
        )

    @property
    def failed_count(self) -> int:
        return sum(
            item.status is EvaluationTrialStatus.FAILED
            for item in self.records
        )


class JsonEvaluationManifestStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> EvaluationRunManifest | None:
        if not self.path.exists():
            return None
        return EvaluationRunManifest.model_validate_json(
            self.path.read_text(encoding="utf-8")
        )

    def save(self, manifest: EvaluationRunManifest) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            manifest.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        temporary.replace(self.path)
