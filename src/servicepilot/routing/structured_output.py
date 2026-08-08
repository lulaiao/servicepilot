"""Shared structured-output prompt and parser for local intent models."""

import json
from typing import Any

from servicepilot.routing.models import IntentResult


def build_intent_prompt(text: str) -> str:
    return (
        "你是订单售后分类器。只输出一个JSON对象，不要解释。"
        "primary_intent只能取 order_query,cancel_order,full_refund,"
        "partial_refund,delivery_delay,missing_or_wrong_item,"
        "duplicate_charge,coupon_issue,reschedule,complaint_escalation,"
        "out_of_scope。secondary_intents是数组。slots必须包含order_id、"
        "reason、requested_amount，未知用null。risk_level取low/medium/high；"
        "confidence为0到1；needs_clarification和injection_detected为布尔值。"
        f"\n用户输入：{text}"
    )


def parse_intent_output(text: str) -> IntentResult:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found")
    value: Any = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("output is not an object")
    return IntentResult.model_validate(value)

