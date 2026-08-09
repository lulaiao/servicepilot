import pytest

from servicepilot.training.diversity import DiversitySample, summarize_diversity


def sample(
    scenario: str, completion: str, reward: float, *, parsed: bool = True
) -> DiversitySample:
    return DiversitySample(
        scenario_id=scenario,
        completion=completion,
        parsed=parsed,
        reward=reward,
    )


def test_valid_reward_variance_allows_smoke_retry() -> None:
    summary = summarize_diversity(
        (
            sample("a", "good", 1.75),
            sample("a", "wrong", -0.5),
            sample("b", "same", 1.75),
            sample("b", "same", 1.75),
        )
    )
    assert summary.valid_nonzero_reward_group_count == 1
    assert summary.eligible_for_smoke_retry


def test_malformed_only_variance_does_not_unlock_retry() -> None:
    samples = tuple(
        sample("a", f"invalid-{index}", -1.0, parsed=False) for index in range(20)
    ) + (sample("a", "valid", 1.75),)
    summary = summarize_diversity(samples)
    assert summary.schema_valid_rate < 0.95
    assert not summary.eligible_for_smoke_retry


def test_empty_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        summarize_diversity(())
