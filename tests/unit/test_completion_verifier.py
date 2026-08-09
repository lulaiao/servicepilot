from servicepilot.agents.completion import OutputCompletionVerifier
from servicepilot.eval.models import Intent, TraceEvent, TraceRole


def tool_event(name: str, ok: bool = True) -> TraceEvent:
    return TraceEvent(
        step=1,
        role=TraceRole.TOOL,
        kind="tool_result",
        content="result",
        tool_name=name,
        result={"ok": ok},
    )


def test_multi_intent_completion_requires_every_successful_tool() -> None:
    verifier = OutputCompletionVerifier()
    denied = verifier.verify(
        (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION),
        (tool_event("report_delivery_issue"),),
    )
    allowed = verifier.verify(
        (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION),
        (tool_event("report_delivery_issue"), tool_event("create_handoff_ticket")),
    )

    assert denied.missing_tools == ("create_handoff_ticket",)
    assert not denied.allowed
    assert allowed.allowed


def test_failed_tool_is_not_completion_evidence() -> None:
    decision = OutputCompletionVerifier().verify(
        (Intent.COUPON_ISSUE,), (tool_event("restore_coupon", ok=False),)
    )
    assert not decision.allowed
