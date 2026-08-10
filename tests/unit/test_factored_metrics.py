from servicepilot.eval.factored_metrics import factored_metrics
from servicepilot.routing.factored_intent import (
    FactoredIntentResult,
    IssueType,
    RequestedAction,
)
from servicepilot.routing.models import RiskLevel


def value(issue: IssueType, *actions: RequestedAction) -> FactoredIntentResult:
    return FactoredIntentResult(
        issue_type=issue,
        requested_actions=actions,
        risk_level=RiskLevel.LOW,
        confidence=1.0,
        needs_clarification=False,
    )


def test_perfect_factored_metrics_are_one_and_safety_errors_zero() -> None:
    targets = [value(IssueType.NONE, RequestedAction.CANCEL_ORDER), value(IssueType.DELIVERY_DELAY)]
    metrics = factored_metrics(targets, targets)

    assert metrics["schema_valid_rate"] == 1.0
    assert metrics["issue_action_exact_match"] == 1.0
    assert metrics["unrequested_action_rate"] == 0.0
    assert metrics["high_risk_action_false_positive_rate"] == 0.0
    assert metrics["legacy_projection_accuracy"] == 1.0


def test_metrics_count_schema_failure_and_unrequested_high_risk_action() -> None:
    targets = [value(IssueType.DELIVERY_DELAY), value(IssueType.NONE)]
    predictions = [
        value(IssueType.DELIVERY_DELAY, RequestedAction.FULL_REFUND),
        None,
    ]
    metrics = factored_metrics(targets, predictions)

    assert metrics["schema_valid_rate"] == 0.5
    assert metrics["issue_accuracy"] == 0.5
    assert metrics["unrequested_action_rate"] == 0.5
    assert metrics["high_risk_action_false_positive_rate"] == 0.5
    assert metrics["issue_action_exact_match"] == 0.0
