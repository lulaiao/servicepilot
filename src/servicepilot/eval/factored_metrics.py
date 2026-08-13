"""Deterministic quality and safety metrics for factored classifier outputs."""

from collections.abc import Sequence

from servicepilot.routing.factored_intent import (
    FactoredIntentResult,
    IssueType,
    RequestedAction,
    project_legacy_intent,
)

_HIGH_RISK_ACTIONS = frozenset(
    {
        RequestedAction.CANCEL_ORDER,
        RequestedAction.FULL_REFUND,
        RequestedAction.PARTIAL_REFUND,
        RequestedAction.RESCHEDULE,
    }
)


def _label_f1(gold: Sequence[set[str]], predicted: Sequence[set[str]], label: str) -> float:
    tp = sum(label in left and label in right for left, right in zip(gold, predicted, strict=True))
    fp = sum(
        label not in left and label in right for left, right in zip(gold, predicted, strict=True)
    )
    fn = sum(
        label in left and label not in right for left, right in zip(gold, predicted, strict=True)
    )
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def factored_metrics(
    targets: Sequence[FactoredIntentResult],
    predictions: Sequence[FactoredIntentResult | None],
) -> dict[str, float | int]:
    if not targets or len(targets) != len(predictions):
        raise ValueError("targets and predictions must have equal non-zero length")
    count = len(targets)
    issue_gold = [{item.issue_type.value} for item in targets]
    issue_pred = [{item.issue_type.value} if item else set() for item in predictions]
    action_gold = [{action.value for action in item.requested_actions} for item in targets]
    action_pred = [
        {action.value for action in item.requested_actions} if item else set()
        for item in predictions
    ]
    issue_macro = sum(_label_f1(issue_gold, issue_pred, label.value) for label in IssueType) / len(
        IssueType
    )
    action_macro = sum(
        _label_f1(action_gold, action_pred, label.value) for label in RequestedAction
    ) / len(RequestedAction)
    action_tp = sum(len(left & right) for left, right in zip(action_gold, action_pred, strict=True))
    action_fp = sum(len(right - left) for left, right in zip(action_gold, action_pred, strict=True))
    action_fn = sum(len(left - right) for left, right in zip(action_gold, action_pred, strict=True))
    action_micro = (
        2 * action_tp / (2 * action_tp + action_fp + action_fn)
        if 2 * action_tp + action_fp + action_fn
        else 0.0
    )
    hallucinated = [right - left for left, right in zip(action_gold, action_pred, strict=True)]
    high_risk_values = {item.value for item in _HIGH_RISK_ACTIONS}
    legacy_correct = 0
    for target, prediction in zip(targets, predictions, strict=True):
        if prediction is None:
            continue
        gold_legacy = project_legacy_intent(target)
        predicted_legacy = project_legacy_intent(prediction)
        if (
            gold_legacy.primary_intent,
            gold_legacy.secondary_intents,
        ) == (
            predicted_legacy.primary_intent,
            predicted_legacy.secondary_intents,
        ):
            legacy_correct += 1
    return {
        "example_count": count,
        "schema_valid_rate": round(sum(item is not None for item in predictions) / count, 4),
        "issue_accuracy": round(
            sum(
                item is not None and item.issue_type is target.issue_type
                for target, item in zip(targets, predictions, strict=True)
            )
            / count,
            4,
        ),
        "issue_macro_f1": round(issue_macro, 4),
        "requested_action_exact_match": round(
            sum(left == right for left, right in zip(action_gold, action_pred, strict=True))
            / count,
            4,
        ),
        "requested_action_micro_f1": round(action_micro, 4),
        "requested_action_macro_f1": round(action_macro, 4),
        "issue_action_exact_match": round(
            sum(
                prediction is not None
                and prediction.issue_type is target.issue_type
                and set(prediction.requested_actions) == set(target.requested_actions)
                for target, prediction in zip(targets, predictions, strict=True)
            )
            / count,
            4,
        ),
        "unrequested_action_rate": round(sum(bool(item) for item in hallucinated) / count, 4),
        "high_risk_action_false_positive_rate": round(
            sum(bool(item & high_risk_values) for item in hallucinated) / count, 4
        ),
        "legacy_projection_accuracy": round(legacy_correct / count, 4),
    }
