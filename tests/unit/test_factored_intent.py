import pytest
from pydantic import ValidationError

from servicepilot.eval.models import Intent
from servicepilot.routing.factored_intent import (
    FactoredIntentResult,
    FactoredSlots,
    IssueType,
    RequestedAction,
    project_legacy_intent,
)
from servicepilot.routing.models import RiskLevel


def result(
    issue: IssueType, *actions: RequestedAction, amount: str | None = None
) -> FactoredIntentResult:
    return FactoredIntentResult(
        issue_type=issue,
        requested_actions=actions,
        slots=FactoredSlots(requested_amount=amount),
        risk_level=RiskLevel.HIGH,
        confidence=1.0,
        needs_clarification=True,
    )


def test_action_only_cancellation_does_not_become_reschedule_or_refund() -> None:
    legacy = project_legacy_intent(result(IssueType.NONE, RequestedAction.CANCEL_ORDER))

    assert legacy.primary_intent is Intent.CANCEL_ORDER
    assert legacy.secondary_intents == ()


@pytest.mark.parametrize(
    ("issue", "expected"),
    [
        (IssueType.MISSING_OR_WRONG_ITEM, Intent.MISSING_OR_WRONG_ITEM),
        (IssueType.DUPLICATE_CHARGE, Intent.DUPLICATE_CHARGE),
    ],
)
def test_incident_remains_primary_and_refund_remedy_is_not_duplicated(
    issue: IssueType, expected: Intent
) -> None:
    legacy = project_legacy_intent(result(issue, RequestedAction.PARTIAL_REFUND, amount="12"))

    assert legacy.primary_intent is expected
    assert legacy.secondary_intents == ()
    assert legacy.slots["requested_amount"] == "12"


def test_independent_complaint_action_is_preserved_as_secondary() -> None:
    legacy = project_legacy_intent(
        result(IssueType.DELIVERY_DELAY, RequestedAction.COMPLAINT_ESCALATION)
    )

    assert legacy.primary_intent is Intent.DELIVERY_DELAY
    assert legacy.secondary_intents == (Intent.COMPLAINT_ESCALATION,)


def test_projection_deduplicates_actions_without_inventing_any() -> None:
    legacy = project_legacy_intent(
        result(
            IssueType.NONE,
            RequestedAction.ORDER_QUERY,
            RequestedAction.ORDER_QUERY,
        )
    )

    assert legacy.primary_intent is Intent.ORDER_QUERY
    assert legacy.secondary_intents == ()


def test_requested_amount_rejects_json_number() -> None:
    with pytest.raises(ValidationError):
        FactoredSlots.model_validate({"requested_amount": 12})
