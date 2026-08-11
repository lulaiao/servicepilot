import json
from collections import Counter

from servicepilot.training.classifier_v7_data import (
    build_classifier_v7_remediation,
    build_classifier_v7_sft,
)
from servicepilot.training.data_models import DataSplit


def category(record_id: str) -> str:
    return record_id.removeprefix("v7-train-").rsplit("-", maxsplit=1)[0]


def test_v7_is_bounded_train_only_and_excludes_v6() -> None:
    new = build_classifier_v7_remediation()
    all_records = build_classifier_v7_sft()

    assert len(new) == 24
    assert all(item.split is DataSplit.TRAIN for item in new)
    assert Counter(category(item.source_record_id) for item in new) == {
        "lifecycle_stop": 8,
        "discount_entitlement_restore": 8,
        "amount_string_contract": 8,
    }
    assert len(all_records) == 180
    assert sum(item.split is DataSplit.TRAIN for item in all_records) == 144
    assert sum(item.split is DataSplit.DEV for item in all_records) == 36
    assert not any(item.source_record_id.startswith("v6-") for item in all_records)


def test_v7_amount_targets_use_string_slots() -> None:
    records = [
        item
        for item in build_classifier_v7_remediation()
        if "amount_string_contract" in item.source_record_id
    ]

    assert all(
        isinstance(json.loads(item.messages[1]["content"])["slots"]["requested_amount"], str)
        for item in records
    )


def test_v7_prompt_explicitly_forbids_numeric_amount() -> None:
    prompt = build_classifier_v7_remediation()[0].messages[0]["content"]

    assert "绝不能输出JSON数字" in prompt
