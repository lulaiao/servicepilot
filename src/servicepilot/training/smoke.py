"""Pure helpers for auditable LoRA smoke-test label masking."""

from collections.abc import Sequence


def assistant_only_labels(
    tokenized_prefixes: Sequence[Sequence[int]], roles: Sequence[str]
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Label only new tokens introduced by assistant messages."""
    if len(tokenized_prefixes) != len(roles):
        raise ValueError("prefix and role counts differ")
    input_ids: list[int] = []
    labels: list[int] = []
    previous_length = 0
    for prefix, role in zip(tokenized_prefixes, roles, strict=True):
        current = list(prefix)
        if current[:previous_length] != input_ids:
            raise ValueError("tokenized message prefixes are not nested")
        delta = current[previous_length:]
        input_ids.extend(delta)
        labels.extend(delta if role == "assistant" else [-100] * len(delta))
        previous_length = len(current)
    if not any(label != -100 for label in labels):
        raise ValueError("no assistant tokens available for training")
    return tuple(input_ids), tuple(labels)
