import json

import pytest
from pydantic import ValidationError

from servicepilot.routing.factored_intent import IssueType, RequestedAction
from servicepilot.routing.structured_output import (
    build_factored_intent_prompt,
    parse_factored_intent_output,
)


def valid_payload() -> dict[str, object]:
    return {
        "issue_type": "missing_or_wrong_item",
        "requested_actions": ["partial_refund"],
        "slots": {"order_id": "SPF001", "reason": "错发", "requested_amount": "12"},
        "risk_level": "high",
        "confidence": 0.9,
        "needs_clarification": False,
        "injection_detected": False,
    }


def test_factored_prompt_defines_issue_action_separation_and_non_invention() -> None:
    prompt = build_factored_intent_prompt("测试输入")

    assert "问题与动作必须分别判断" in prompt
    assert "不得补充用户未明确请求的操作" in prompt
    assert "绝不能输出JSON数字" in prompt
    assert prompt.endswith("用户输入：测试输入")


def test_factored_parser_accepts_surrounding_text_but_returns_typed_result() -> None:
    result = parse_factored_intent_output(f"prefix {json.dumps(valid_payload())} suffix")

    assert result.issue_type is IssueType.MISSING_OR_WRONG_ITEM
    assert result.requested_actions == (RequestedAction.PARTIAL_REFUND,)
    assert result.slots.requested_amount == "12"


def test_factored_parser_rejects_number_amount_and_unknown_action() -> None:
    numeric = valid_payload()
    numeric["slots"] = {"order_id": None, "reason": None, "requested_amount": 12}
    with pytest.raises(ValidationError):
        parse_factored_intent_output(json.dumps(numeric))

    unknown = valid_payload()
    unknown["requested_actions"] = ["delete_database"]
    with pytest.raises(ValidationError):
        parse_factored_intent_output(json.dumps(unknown))


def test_factored_parser_rejects_missing_object() -> None:
    with pytest.raises(ValueError, match="no JSON object"):
        parse_factored_intent_output("not json")
