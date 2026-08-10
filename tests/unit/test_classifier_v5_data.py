import json
from collections import Counter

from servicepilot.training.classifier_v5_data import (
    build_classifier_v5_hard_negatives,
    build_classifier_v5_sft,
)
from servicepilot.training.data_models import DataSplit


def test_v5_adds_only_bounded_train_hard_negatives() -> None:
    hard = build_classifier_v5_hard_negatives()
    counts = Counter(item.source_record_id.split("-")[2] for item in hard)

    assert len(hard) == 48
    assert all(item.split is DataSplit.TRAIN for item in hard)
    assert len({item.record_id for item in hard}) == len(hard)
    assert counts == {
        "cancel_not_reschedule": 12,
        "reschedule_not_cancel": 12,
        "delay_and_escalation": 24,
    }


def test_v5_multi_intent_targets_require_secondary_completion() -> None:
    multi = [
        item
        for item in build_classifier_v5_hard_negatives()
        if "delay_and_escalation" in item.source_record_id
    ]
    outputs = [json.loads(item.messages[1]["content"]) for item in multi]

    assert all(item["primary_intent"] == "delivery_delay" for item in outputs)
    assert all(item["secondary_intents"] == ["complaint_escalation"] for item in outputs)


def test_v5_preserves_v4_dev_and_has_no_sealed_records() -> None:
    records = build_classifier_v5_sft()

    assert len(records) == 156
    assert sum(item.split is DataSplit.TRAIN for item in records) == 120
    assert sum(item.split is DataSplit.DEV for item in records) == 36
    assert sum(item.split is DataSplit.SEALED_TEST for item in records) == 0
