from collections import Counter

from servicepilot.eval.models import Intent
from servicepilot.training.multilabel_composition_v2_data import (
    build_multilabel_composition_v2,
)


def test_v2_is_balanced_family_split_and_has_all_label_combinations() -> None:
    records = build_multilabel_composition_v2()

    assert len(records) == 640
    assert len({item.record_id for item in records}) == 640
    assert len({item.text for item in records}) == 640
    assert len({item.family_id for item in records}) == 320
    assert Counter(item.split for item in records) == {"train": 512, "dev": 128}
    assert Counter(item.category for item in records) == {
        f"label_set_{bits:03b}": 80 for bits in range(8)
    }
    assert Counter(label for item in records for label in item.labels) == {
        Intent.DELIVERY_DELAY: 320,
        Intent.COMPLAINT_ESCALATION: 320,
        Intent.PARTIAL_REFUND: 320,
    }


def test_v2_variants_never_cross_splits_and_no_signature_crosses_splits() -> None:
    records = build_multilabel_composition_v2()
    family_splits: dict[str, set[str]] = {}
    for item in records:
        family_splits.setdefault(item.family_id, set()).add(item.split)
    assert all(len(splits) == 1 for splits in family_splits.values())

    train_signatures = {item.semantic_signature_sha256 for item in records if item.split == "train"}
    dev_signatures = {item.semantic_signature_sha256 for item in records if item.split == "dev"}
    assert not train_signatures & dev_signatures
