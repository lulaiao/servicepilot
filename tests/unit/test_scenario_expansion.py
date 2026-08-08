import pytest

from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.training import DataSplit, build_phase9_sealed_families


def test_sealed_family_catalog_is_unique_and_independently_reserved() -> None:
    families = build_phase9_sealed_families()

    assert len(families) == 40
    assert len({item.family_id for item in families}) == 40
    assert len({item.semantic_signature_sha256 for item in families}) == 40
    assert all(item.split is DataSplit.SEALED_TEST for item in families)
    assert all(item.provenance == "independently_authored_phase9_sealed_v1" for item in families)


@pytest.mark.asyncio
async def test_first_sealed_family_batch_is_executable() -> None:
    harness = EvaluationHarness()
    failures = []
    for family in build_phase9_sealed_families():
        _, judge, _ = await harness.run_scenario(family.canonical_scenario)
        if not judge.task_success:
            failures.append((family.family_id, judge.failure_reasons))

    assert failures == []
