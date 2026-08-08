import pytest

from servicepilot.training import assistant_only_labels


def test_assistant_only_labels_masks_non_assistant_prefixes() -> None:
    input_ids, labels = assistant_only_labels(
        ((1, 2), (1, 2, 3, 4), (1, 2, 3, 4, 5)),
        ("user", "assistant", "tool"),
    )

    assert input_ids == (1, 2, 3, 4, 5)
    assert labels == (-100, -100, 3, 4, -100)


def test_assistant_only_labels_rejects_non_nested_or_unlabelled_data() -> None:
    with pytest.raises(ValueError, match="not nested"):
        assistant_only_labels(((1, 2), (1, 3)), ("user", "assistant"))
    with pytest.raises(ValueError, match="no assistant"):
        assistant_only_labels(((1, 2),), ("user",))
