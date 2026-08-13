import json
from collections import Counter

from servicepilot.routing.factored_intent import FactoredIntentResult, project_legacy_intent
from servicepilot.training.data_models import DataSplit
from servicepilot.training.factored_classifier_catalog import (
    FACTORED_FAMILIES,
    build_factored_classifier_sft,
)


def test_factored_catalog_has_family_isolated_balanced_splits() -> None:
    records = build_factored_classifier_sft()
    counts = Counter(item.split for item in records)

    assert len(FACTORED_FAMILIES) == 14
    assert counts == {DataSplit.TRAIN: 56, DataSplit.DEV: 28}
    assert len({item.record_id for item in records}) == len(records)
    train_families = {
        item.source_record_id.split("-")[2] for item in records if item.split is DataSplit.TRAIN
    }
    dev_families = {
        item.source_record_id.split("-")[2] for item in records if item.split is DataSplit.DEV
    }
    assert train_families == dev_families


def test_every_completion_is_typed_and_projects_deterministically() -> None:
    for record in build_factored_classifier_sft():
        result = FactoredIntentResult.model_validate_json(record.messages[1]["content"])
        legacy = project_legacy_intent(result)

        assert legacy.confidence == 1.0
        assert isinstance(result.requested_actions, tuple)


def test_visible_amounts_are_serialized_as_strings() -> None:
    amount_records = [
        item
        for item in build_factored_classifier_sft()
        if "元" in item.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1]
    ]

    assert amount_records
    assert all(
        isinstance(json.loads(item.messages[1]["content"])["slots"]["requested_amount"], str)
        for item in amount_records
    )
