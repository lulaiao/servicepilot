from servicepilot.training import (
    TrainingExperiment,
    TrainingReadinessInput,
    assess_training_readiness,
)


def current_audit(**updates: object) -> TrainingReadinessInput:
    return TrainingReadinessInput(
        cuda_available=True,
        gpu_vram_mib=49140,
        free_disk_gib=3481.6,
        train_sft_records=24,
        dev_sft_records=6,
        sealed_sft_records=6,
        train_preference_records=33,
    ).model_copy(update=updates)


def test_current_resources_allow_only_smoke_training() -> None:
    results = {item.experiment: item for item in assess_training_readiness(current_audit())}

    assert results[TrainingExperiment.LORA_SMOKE].allowed
    assert not results[TrainingExperiment.LORA_SFT].allowed
    assert "fewer_than_500_train_sft_records" in results[TrainingExperiment.LORA_SFT].failed_gates
    assert not results[TrainingExperiment.OUTCOME_GRPO].allowed
    assert "reward_unit_tests_missing" in results[TrainingExperiment.OUTCOME_GRPO].failed_gates


def test_full_training_requires_resources_data_and_reward_audits() -> None:
    ready = current_audit(
        train_sft_records=500,
        dev_sft_records=100,
        sealed_sft_records=100,
        train_preference_records=500,
        reward_unit_tests_passed=True,
        reward_distribution_audited=True,
        reward_hacking_audited=True,
        grpo_deployment_contract_validated=True,
    )

    assert all(item.allowed for item in assess_training_readiness(ready))


def test_reward_audit_alone_does_not_authorize_objective_mismatch() -> None:
    audited = current_audit(
        train_sft_records=500,
        dev_sft_records=100,
        sealed_sft_records=100,
        train_preference_records=500,
        reward_unit_tests_passed=True,
        reward_distribution_audited=True,
        reward_hacking_audited=True,
    )
    results = {item.experiment: item for item in assess_training_readiness(audited)}
    assert not results[TrainingExperiment.OUTCOME_GRPO].allowed
    assert (
        "grpo_deployment_contract_not_validated"
        in results[TrainingExperiment.OUTCOME_GRPO].failed_gates
    )
