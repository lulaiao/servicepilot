"""Factored issue/action classifier contract and deterministic legacy projection."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from servicepilot.eval.models import Intent
from servicepilot.routing.models import IntentResult, RiskLevel


class IssueType(StrEnum):
    NONE = "none"
    DELIVERY_DELAY = "delivery_delay"
    MISSING_OR_WRONG_ITEM = "missing_or_wrong_item"
    DUPLICATE_CHARGE = "duplicate_charge"
    COUPON_ISSUE = "coupon_issue"
    OUT_OF_SCOPE = "out_of_scope"


class RequestedAction(StrEnum):
    ORDER_QUERY = "order_query"
    CANCEL_ORDER = "cancel_order"
    FULL_REFUND = "full_refund"
    PARTIAL_REFUND = "partial_refund"
    RESCHEDULE = "reschedule"
    COMPLAINT_ESCALATION = "complaint_escalation"


class FactoredSlots(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str | None = None
    reason: str | None = None
    requested_amount: str | None = None


class FactoredIntentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    issue_type: IssueType
    requested_actions: tuple[RequestedAction, ...] = ()
    slots: FactoredSlots = Field(default_factory=FactoredSlots)
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    needs_clarification: bool
    injection_detected: bool = False


_ISSUE_TO_INTENT = {
    IssueType.DELIVERY_DELAY: Intent.DELIVERY_DELAY,
    IssueType.MISSING_OR_WRONG_ITEM: Intent.MISSING_OR_WRONG_ITEM,
    IssueType.DUPLICATE_CHARGE: Intent.DUPLICATE_CHARGE,
    IssueType.COUPON_ISSUE: Intent.COUPON_ISSUE,
    IssueType.OUT_OF_SCOPE: Intent.OUT_OF_SCOPE,
}
_ACTION_TO_INTENT = {action: Intent(action.value) for action in RequestedAction}
_INCIDENT_REMEDIATION = {
    IssueType.MISSING_OR_WRONG_ITEM: frozenset(
        {RequestedAction.FULL_REFUND, RequestedAction.PARTIAL_REFUND}
    ),
    IssueType.DUPLICATE_CHARGE: frozenset(
        {RequestedAction.FULL_REFUND, RequestedAction.PARTIAL_REFUND}
    ),
}


def project_legacy_intent(result: FactoredIntentResult) -> IntentResult:
    """Project without inventing actions or duplicating incident-owned refund handling."""

    issue_intent = _ISSUE_TO_INTENT.get(result.issue_type)
    actions = tuple(dict.fromkeys(result.requested_actions))
    if issue_intent is not None:
        primary = issue_intent
    elif actions:
        primary = _ACTION_TO_INTENT[actions[0]]
    else:
        primary = Intent.OUT_OF_SCOPE

    remediation = _INCIDENT_REMEDIATION.get(result.issue_type, frozenset())
    secondary = []
    for action in actions:
        intent = _ACTION_TO_INTENT[action]
        if intent == primary or action in remediation:
            continue
        if intent not in secondary:
            secondary.append(intent)

    return IntentResult(
        primary_intent=primary,
        secondary_intents=tuple(secondary),
        slots=result.slots.model_dump(mode="json"),
        risk_level=result.risk_level,
        confidence=result.confidence,
        needs_clarification=result.needs_clarification,
        injection_detected=result.injection_detected,
    )
