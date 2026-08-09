"""Frozen contracts and safety checks for Phase 9 LoRA SFT experiments."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoraProtocol(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank: int = Field(gt=0)
    alpha: int = Field(gt=0)
    dropout: float = Field(ge=0, lt=1)
    target_modules: tuple[str, ...]


class SFTBudget(BaseModel):
    model_config = ConfigDict(frozen=True)

    dtype: Literal["bfloat16"]
    max_length: int = Field(gt=0)
    per_device_batch_size: int = Field(gt=0)
    gradient_accumulation_steps: int = Field(gt=0)
    max_epochs: int = Field(gt=0, le=3)
    learning_rate: float = Field(gt=0)
    warmup_ratio: float = Field(ge=0, lt=1)
    max_gradient_norm: float = Field(gt=0)
    checkpoint_every_steps: int = Field(gt=0)
    early_stopping_patience: int = Field(ge=0)


class SFTExperimentProtocol(BaseModel):
    model_config = ConfigDict(frozen=True)

    protocol_version: str
    model_repo: str
    model_revision: str
    data_manifest: str
    train_data: str
    train_sha256: str
    split_counts: dict[str, int]
    seeds: tuple[int, ...]
    lora: LoraProtocol
    budget: SFTBudget
    checkpoint_selection: tuple[str, ...]
    sealed_used_for_selection: bool
    sealed_execution: str
    baseline: str
    required_metrics: tuple[str, ...]
    termination_conditions: tuple[str, ...]
    screening_seed: int | None = None
    screening_max_steps: int | None = Field(default=None, gt=0)
    harness_revision: str | None = None
    required_override_metrics: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_evidence_protocol(self) -> "SFTExperimentProtocol":
        if len(self.seeds) < 4 or len(set(self.seeds)) != len(self.seeds):
            raise ValueError("at least four unique seeds are required")
        if self.sealed_used_for_selection:
            raise ValueError("sealed test cannot select checkpoints or hyperparameters")
        if set(self.split_counts) != {"train", "dev", "sealed_test"}:
            raise ValueError("train/dev/sealed split counts are required")
        if any(count <= 0 for count in self.split_counts.values()):
            raise ValueError("all split counts must be positive")
        if not self.checkpoint_selection or self.checkpoint_selection[0] != "zero_high_risk_error":
            raise ValueError("safety must be the first checkpoint-selection criterion")
        if "peak_vram_mib" not in self.required_metrics:
            raise ValueError("resource evidence must include peak VRAM")
        if (self.screening_seed is None) != (self.screening_max_steps is None):
            raise ValueError("screening seed and max steps must be declared together")
        if self.screening_seed is not None and self.screening_seed not in self.seeds:
            raise ValueError("screening seed must be one of the formal seeds")
        if self.harness_revision and not self.required_override_metrics:
            raise ValueError("versioned Harness requires override metrics")
        return self
