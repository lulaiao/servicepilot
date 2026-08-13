"""Deterministic component metrics for structured intent extractors."""

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.models import Intent
from servicepilot.eval.routing_dataset import DatasetSplit, RoutingExample
from servicepilot.routing.models import IntentResult


class RoutingMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    example_count: int
    primary_accuracy: float
    macro_f1: float
    secondary_exact_match: float
    slot_exact_match: float
    schema_valid_rate: float
    high_risk_error_rate: float


def evaluate_extractor(
    examples: tuple[RoutingExample, ...],
    extractor: Callable[[str], IntentResult],
    split: DatasetSplit,
) -> RoutingMetrics:
    selected = tuple(item for item in examples if item.split is split)
    predictions = tuple(extractor(item.text) for item in selected)
    labels = tuple(item.primary_intent for item in selected)
    predicted_labels = tuple(item.primary_intent for item in predictions)
    intents = set(labels) | set(predicted_labels)
    f1_scores: list[float] = []
    for intent in intents:
        true_positive = sum(
            gold is intent and predicted is intent
            for gold, predicted in zip(labels, predicted_labels, strict=True)
        )
        false_positive = sum(
            gold is not intent and predicted is intent
            for gold, predicted in zip(labels, predicted_labels, strict=True)
        )
        false_negative = sum(
            gold is intent and predicted is not intent
            for gold, predicted in zip(labels, predicted_labels, strict=True)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        f1_scores.append(2 * true_positive / denominator if denominator else 0)
    high_risk = {
        Intent.CANCEL_ORDER,
        Intent.FULL_REFUND,
        Intent.PARTIAL_REFUND,
        Intent.MISSING_OR_WRONG_ITEM,
        Intent.DUPLICATE_CHARGE,
        Intent.RESCHEDULE,
    }
    high_risk_count = sum(label in high_risk for label in labels)
    high_risk_errors = sum(
        gold in high_risk and predicted is not gold
        for gold, predicted in zip(labels, predicted_labels, strict=True)
    )
    return RoutingMetrics(
        example_count=len(selected),
        primary_accuracy=round(
            sum(gold is predicted for gold, predicted in zip(labels, predicted_labels, strict=True))
            / len(selected),
            4,
        ),
        macro_f1=round(sum(f1_scores) / len(f1_scores), 4),
        secondary_exact_match=round(
            sum(
                set(example.secondary_intents) == set(prediction.secondary_intents)
                for example, prediction in zip(selected, predictions, strict=True)
            )
            / len(selected),
            4,
        ),
        slot_exact_match=round(
            sum(
                all(prediction.slots.get(key) == value for key, value in example.slots.items())
                for example, prediction in zip(selected, predictions, strict=True)
            )
            / len(selected),
            4,
        ),
        schema_valid_rate=1.0,
        high_risk_error_rate=round(
            high_risk_errors / high_risk_count if high_risk_count else 0,
            4,
        ),
    )
