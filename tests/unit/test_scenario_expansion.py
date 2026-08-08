import pytest

from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.training import (
    DataSplit,
    build_phase9_sealed_families,
    build_phase9_train_dev_families,
    expand_family_variants,
)


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


@pytest.mark.asyncio
async def test_variants_preserve_family_split_and_authoritative_outcome() -> None:
    family = build_phase9_train_dev_families()[0]
    variants = expand_family_variants(family)

    assert len(variants) == 3
    assert len({item.variant_id for item in variants}) == 3
    assert len({item.utterance_sha256 for item in variants}) == 3
    assert all(item.family_id == family.family_id for item in variants)
    assert all(item.split is family.split for item in variants)
    assert all(
        item.semantic_signature_sha256 == family.semantic_signature_sha256 for item in variants
    )

    harness = EvaluationHarness()
    for variant in variants:
        _, judge, _ = await harness.run_scenario(variant.scenario)
        assert judge.task_success, (variant.variant_id, judge.failure_reasons)


@pytest.mark.asyncio
async def test_first_train_dev_batch_is_unique_nonleaking_and_executable() -> None:
    sealed_signatures = {item.semantic_signature_sha256 for item in build_phase9_sealed_families()}
    families = build_phase9_train_dev_families()
    assert len(families) >= 50
    assert {item.split for item in families} == {DataSplit.TRAIN, DataSplit.DEV}
    assert len({item.semantic_signature_sha256 for item in families}) == len(families)
    assert not sealed_signatures & {item.semantic_signature_sha256 for item in families}

    harness = EvaluationHarness()
    failures = []
    for family in families:
        _, judge, _ = await harness.run_scenario(family.canonical_scenario)
        if not judge.task_success:
            failures.append((family.family_id, judge.failure_reasons))
    assert failures == []
