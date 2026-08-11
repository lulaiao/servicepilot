from collections import Counter

from servicepilot.eval.models import Intent
from servicepilot.training.multilabel_composition_data import build_multilabel_composition_v1


def test_multilabel_data_is_family_split_and_balanced() -> None:
    records = build_multilabel_composition_v1()
    train = [item for item in records if item.split == "train"]
    dev = [item for item in records if item.split == "dev"]

    assert len(records) == 240
    assert len(train) == 192
    assert len(dev) == 48
    assert len({item.family_id for item in train}) == 64
    assert len({item.family_id for item in dev}) == 16
    assert not {item.family_id for item in train} & {item.family_id for item in dev}
    assert not {item.semantic_signature_sha256 for item in train} & {
        item.semantic_signature_sha256 for item in dev
    }


def test_multilabel_data_covers_positive_negative_and_three_intent() -> None:
    records = build_multilabel_composition_v1()
    categories = Counter(item.category for item in records)

    assert categories == {
        "explicit_pair": 60,
        "three_intent": 30,
        "delivery_only": 30,
        "negated_escalation": 30,
        "conditional_future": 30,
        "historical_request": 30,
        "escalation_only": 15,
        "unrelated": 15,
    }
    assert any(len(item.labels) == 3 for item in records)
    assert any(not item.labels for item in records)
    assert set(label for item in records for label in item.labels) == {
        Intent.DELIVERY_DELAY,
        Intent.COMPLAINT_ESCALATION,
        Intent.PARTIAL_REFUND,
    }
