"""Metrics for inference-only GRPO generation-diversity diagnostics."""

import statistics

from pydantic import BaseModel, ConfigDict


class DiversitySample(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    completion: str
    parsed: bool
    reward: float
    hard_gate: str | None = None


class DiversitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_count: int
    scenario_count: int
    schema_valid_rate: float
    unique_completion_rate: float
    nonzero_reward_group_count: int
    valid_nonzero_reward_group_count: int
    unsafe_hard_gate_rate: float
    eligible_for_smoke_retry: bool


def summarize_diversity(samples: tuple[DiversitySample, ...]) -> DiversitySummary:
    if not samples:
        raise ValueError("at least one diversity sample is required")
    by_scenario: dict[str, list[DiversitySample]] = {}
    for sample in samples:
        by_scenario.setdefault(sample.scenario_id, []).append(sample)
    nonzero_groups = 0
    valid_nonzero_groups = 0
    for group in by_scenario.values():
        if len(group) > 1 and statistics.pstdev(item.reward for item in group) > 0:
            nonzero_groups += 1
        valid_rewards = [item.reward for item in group if item.parsed]
        if len(valid_rewards) > 1 and statistics.pstdev(valid_rewards) > 0:
            valid_nonzero_groups += 1
    schema_valid_rate = sum(item.parsed for item in samples) / len(samples)
    unsafe_rate = sum(item.hard_gate == "unsafe" for item in samples) / len(samples)
    unique_rate = len({item.completion for item in samples}) / len(samples)
    eligible = (
        schema_valid_rate >= 0.95
        and valid_nonzero_groups > 0
        and unsafe_rate <= 0.1
    )
    return DiversitySummary(
        sample_count=len(samples),
        scenario_count=len(by_scenario),
        schema_valid_rate=round(schema_valid_rate, 6),
        unique_completion_rate=round(unique_rate, 6),
        nonzero_reward_group_count=nonzero_groups,
        valid_nonzero_reward_group_count=valid_nonzero_groups,
        unsafe_hard_gate_rate=round(unsafe_rate, 6),
        eligible_for_smoke_retry=eligible,
    )
