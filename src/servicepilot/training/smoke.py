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
    for prefix, role in zip(tokenized_prefixes, roles, strict=True):
        current = list(prefix)
        common = 0
        for old_token, new_token in zip(input_ids, current, strict=False):
            if old_token != new_token:
                break
            common += 1
        # Chat templates may rewrite the prior end-of-turn marker when another
        # message is appended. Rewind that unstable suffix before labelling the
        # newly rendered suffix; the final input always exactly matches the
        # tokenizer's full-conversation rendering.
        del input_ids[common:]
        del labels[common:]
        delta = current[common:]
        input_ids.extend(delta)
        labels.extend(delta if role == "assistant" else [-100] * len(delta))
    if not any(label != -100 for label in labels):
        raise ValueError("no assistant tokens available for training")
    return tuple(input_ids), tuple(labels)
