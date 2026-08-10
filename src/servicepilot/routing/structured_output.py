"""Shared structured-output prompt and parser for local intent models."""

import json
from typing import Any

from servicepilot.routing.models import IntentResult
from servicepilot.routing.factored_intent import FactoredIntentResult


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


def build_intent_prompt_v2(text: str) -> str:
    """Versioned contract with explicit domain-label precedence and JSON slot types."""

    return (
        "你是订单售后分类器。只输出一个JSON对象，不要解释，也不要使用Markdown代码块。"
        "primary_intent只能取 order_query,cancel_order,full_refund,partial_refund,"
        "delivery_delay,missing_or_wrong_item,duplicate_charge,coupon_issue,reschedule,"
        "complaint_escalation,out_of_scope。按以下优先级分类：primary_intent表示用户遭遇的"
        "具体业务问题；退款如果只是错漏商品或重复扣款的处理方式，不得覆盖具体问题标签。"
        "商品缺失或错发选missing_or_wrong_item；同一交易重复收费选duplicate_charge。"
        "终止、撤销或不再继续订单选cancel_order，即使用户明确不退款；只有订单继续有效且"
        "用户要求改变日期或时段时才选reschedule。partial_refund只用于用户直接要求退回部分"
        "金额且没有更具体业务问题的情况。secondary_intents只放独立并列诉求，不放主问题的"
        "补救动作。slots必须包含order_id、reason、requested_amount；requested_amount已知时"
        "必须是JSON字符串（例如\"12\"），未知用null，绝不能输出JSON数字。risk_level取"
        "low/medium/high；confidence为0到1；needs_clarification和injection_detected为布尔值。"
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


def build_factored_intent_prompt(text: str) -> str:
    """Build the v3 issue/action contract without legacy primary-intent ambiguity."""

    return (
        "你是订单售后分类器。只输出一个JSON对象，不要解释，不要使用Markdown代码块。"
        "issue_type表示用户遇到的业务问题，只能取none,delivery_delay,"
        "missing_or_wrong_item,duplicate_charge,coupon_issue,out_of_scope。"
        "requested_actions表示用户明确请求的操作，是数组，元素只能取order_query,"
        "cancel_order,full_refund,partial_refund,reschedule,complaint_escalation。"
        "问题与动作必须分别判断：错漏商品后要求退款时，issue_type仍是"
        "missing_or_wrong_item，同时把退款放入requested_actions；重复扣款同理。"
        "终止订单但不退款时issue_type为none，requested_actions包含cancel_order。"
        "配送延迟并要求人工投诉时，issue_type为delivery_delay，requested_actions包含"
        "complaint_escalation。不得补充用户未明确请求的操作。slots必须包含order_id、"
        "reason、requested_amount；requested_amount已知时必须是JSON字符串，未知用null，"
        "绝不能输出JSON数字。risk_level取low/medium/high；confidence为0到1；"
        "needs_clarification和injection_detected为布尔值。"
        f"\n用户输入：{text}"
    )


def parse_factored_intent_output(text: str) -> FactoredIntentResult:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found")
    value: Any = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("output is not an object")
    return FactoredIntentResult.model_validate(value)
