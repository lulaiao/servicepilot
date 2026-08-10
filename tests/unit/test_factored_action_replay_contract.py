from servicepilot.eval.factored_metrics import factored_metrics
from servicepilot.routing.action_evidence import bind_evidence_backed_actions
from servicepilot.routing.factored_intent import FactoredIntentResult, IssueType, RequestedAction
from servicepilot.routing.models import RiskLevel


def value(issue: IssueType, *actions: RequestedAction) -> FactoredIntentResult:
    return FactoredIntentResult(
        issue_type=issue,
        requested_actions=actions,
        risk_level=RiskLevel.HIGH,
        confidence=1.0,
        needs_clarification=False,
    )


def test_binding_replay_changes_only_actions_and_removes_high_risk_false_positive() -> None:
    target = value(IssueType.DUPLICATE_CHARGE)
    raw = value(IssueType.DUPLICATE_CHARGE, RequestedAction.CANCEL_ORDER)
    bound = bind_evidence_backed_actions(raw, "同一交易发生重复扣款")
    metrics = factored_metrics([target], [bound])

    assert bound.issue_type is raw.issue_type
    assert bound.slots == raw.slots
    assert metrics["high_risk_action_false_positive_rate"] == 0.0
    assert metrics["issue_action_exact_match"] == 1.0
