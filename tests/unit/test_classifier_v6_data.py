import json
from collections import Counter

from servicepilot.training.classifier_v6_data import (
    LABEL_BOUNDARY_RULES,
    build_classifier_v6_label_boundaries,
    build_classifier_v6_sft,
)
from servicepilot.training.data_models import DataSplit


def test_v6_adds_balanced_train_only_label_boundaries() -> None:
    records = build_classifier_v6_label_boundaries()
    counts = Counter(item.source_record_id.split("-")[2] for item in records)

    assert len(records) == 48
    assert all(item.split is DataSplit.TRAIN for item in records)
    assert len({item.record_id for item in records}) == len(records)
    assert counts == {
        "cancel_without_refund": 12,
        "missing_item_primary": 12,
        "duplicate_charge_primary": 12,
        "direct_partial_refund": 12,
    }
    assert len(LABEL_BOUNDARY_RULES) == 5


def test_v6_domain_incidents_remain_primary_and_amounts_are_strings() -> None:
    records = build_classifier_v6_label_boundaries()
    by_category = {
        category: [
            json.loads(item.messages[1]["content"])
            for item in records
            if category in item.source_record_id
        ]
        for category in ("missing_item_primary", "duplicate_charge_primary")
    }

    assert all(
        item["primary_intent"] == "missing_or_wrong_item" and item["secondary_intents"] == []
        for item in by_category["missing_item_primary"]
    )
    assert all(
        item["primary_intent"] == "duplicate_charge" and item["secondary_intents"] == []
        for item in by_category["duplicate_charge_primary"]
    )
    assert all(
        isinstance(item["slots"]["requested_amount"], str)
        for outputs in by_category.values()
        for item in outputs
    )


def test_v6_preserves_v4_dev_and_has_no_sealed_records() -> None:
    records = build_classifier_v6_sft()

    assert len(records) == 204
    assert sum(item.split is DataSplit.TRAIN for item in records) == 168
    assert sum(item.split is DataSplit.DEV for item in records) == 36
    assert sum(item.split is DataSplit.SEALED_TEST for item in records) == 0
