"""Deterministic Phase 9 training-readiness gates."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TrainingExperiment(StrEnum):
    LORA_SMOKE = "lora_smoke"
    LORA_SFT = "lora_sft"
    OUTCOME_GRPO = "outcome_grpo"
    PROCESS_GRPO = "process_reward_grpo"


class TrainingReadinessInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    cuda_available: bool
    gpu_vram_mib: int = Field(ge=0)
    free_disk_gib: float = Field(ge=0)
    train_sft_records: int = Field(ge=0)
    dev_sft_records: int = Field(ge=0)
    sealed_sft_records: int = Field(ge=0)
    train_preference_records: int = Field(ge=0)
    reward_unit_tests_passed: bool = False
    reward_distribution_audited: bool = False
    reward_hacking_audited: bool = False
    outcome_grpo_deployment_contract_validated: bool = False
    process_grpo_deployment_contract_validated: bool = False


class ExperimentReadiness(BaseModel):
    model_config = ConfigDict(frozen=True)

    experiment: TrainingExperiment
    allowed: bool
    failed_gates: tuple[str, ...]


def assess_training_readiness(
    current: TrainingReadinessInput,
) -> tuple[ExperimentReadiness, ...]:
    """Apply project gates; thresholds are evidence policy, not universal minima."""
    resource_failures = []
    if not current.cuda_available:
        resource_failures.append("cuda_unavailable")
    if current.gpu_vram_mib < 40_000:
        resource_failures.append("less_than_40_gib_vram")
    if current.free_disk_gib < 100:
        resource_failures.append("less_than_100_gib_free_disk")

    smoke_failures = tuple(resource_failures)
    sft_failures = list(resource_failures)
    if current.train_sft_records < 500:
        sft_failures.append("fewer_than_500_train_sft_records")
    if current.dev_sft_records < 100:
        sft_failures.append("fewer_than_100_dev_sft_records")
    if current.sealed_sft_records < 100:
        sft_failures.append("fewer_than_100_sealed_sft_records")

    grpo_failures = list(sft_failures)
    if current.train_preference_records < 500:
        grpo_failures.append("fewer_than_500_train_preference_records")
    if not current.reward_unit_tests_passed:
        grpo_failures.append("reward_unit_tests_missing")
    if not current.reward_distribution_audited:
        grpo_failures.append("reward_distribution_audit_missing")
    if not current.reward_hacking_audited:
        grpo_failures.append("reward_hacking_audit_missing")
    outcome_grpo_failures = list(grpo_failures)
    if not current.outcome_grpo_deployment_contract_validated:
        outcome_grpo_failures.append("outcome_grpo_deployment_contract_not_validated")
    process_grpo_failures = list(grpo_failures)
    if not current.process_grpo_deployment_contract_validated:
        process_grpo_failures.append("process_grpo_deployment_contract_not_validated")

    return (
        ExperimentReadiness(
            experiment=TrainingExperiment.LORA_SMOKE,
            allowed=not smoke_failures,
            failed_gates=smoke_failures,
        ),
        ExperimentReadiness(
            experiment=TrainingExperiment.LORA_SFT,
            allowed=not sft_failures,
            failed_gates=tuple(sft_failures),
        ),
        ExperimentReadiness(
            experiment=TrainingExperiment.OUTCOME_GRPO,
            allowed=not outcome_grpo_failures,
            failed_gates=tuple(outcome_grpo_failures),
        ),
        ExperimentReadiness(
            experiment=TrainingExperiment.PROCESS_GRPO,
            allowed=not process_grpo_failures,
            failed_gates=tuple(process_grpo_failures),
        ),
    )
