"""Deterministic requested-action extraction with auditable text evidence."""

import re
from dataclasses import dataclass

from servicepilot.routing.factored_intent import FactoredIntentResult, RequestedAction


@dataclass(frozen=True)
class ActionEvidence:
    action: RequestedAction
    text: str
    start: int
    end: int


_PATTERNS: tuple[tuple[RequestedAction, tuple[re.Pattern[str], ...]], ...] = (
    (RequestedAction.ORDER_QUERY, (
        re.compile(r"(?:查询|核实|读取|看看|了解|告知).{0,30}(?:进度|状态|环节|节点|到哪一步|进展)"),
        re.compile(r"(?:进展|履约节点).{0,8}(?:是什么|到哪|告知)"),
    )),
    (RequestedAction.CANCEL_ORDER, (
        re.compile(r"(?:取消|关闭|终止|撤销|作废)(?:这笔|当前|本次)?(?:订单|交易|购买)?"),
        re.compile(r"(?:停止后续履约|不再保留这次购买|不再继续)"),
    )),
    (RequestedAction.FULL_REFUND, (
        re.compile(r"(?:全额退款|全款退回|整单退款|完整支付额退款|全部金额|所有费用都返还)"),
    )),
    (RequestedAction.PARTIAL_REFUND, (
        re.compile(r"(?:部分退款|局部退款|只退款|仅退款|退我|退款|退回|返还)"),
    )),
    (RequestedAction.RESCHEDULE, (
        re.compile(r"(?:改到|调整配送日期|调整.*时段|时段换到|重新预约|换一个配送时段|安排改到)"),
    )),
    (RequestedAction.COMPLAINT_ESCALATION, (
        re.compile(r"(?:人工投诉|正式投诉|投诉工单|升级人工|升级给客服|升级到专员|客服专员介入|人工客服跟进|人工团队介入|转交客服主管)"),
    )),
)
_NEGATION = re.compile(r"(?:不要|不做|不再|无需|暂不|暂时不|先不|没有|还没|未决定)")


def _is_negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 12) : start]
    return bool(_NEGATION.search(prefix[-5:]) or "还没决定是否" in prefix)


def extract_requested_action_evidence(text: str) -> tuple[ActionEvidence, ...]:
    """Return only directly supported actions; full refund dominates partial refund evidence."""

    evidence = []
    for action, patterns in _PATTERNS:
        for pattern in patterns:
            match = pattern.search(text)
            if match and not _is_negated(text, match.start()):
                if action is RequestedAction.CANCEL_ORDER and text[match.end() : match.end() + 1] in {"后", "了"}:
                    continue
                evidence.append(ActionEvidence(action, match.group(0), match.start(), match.end()))
                break
    actions = {item.action for item in evidence}
    if RequestedAction.FULL_REFUND in actions:
        evidence = [item for item in evidence if item.action is not RequestedAction.PARTIAL_REFUND]
    return tuple(evidence)


def extract_requested_actions(text: str) -> tuple[RequestedAction, ...]:
    return tuple(item.action for item in extract_requested_action_evidence(text))


def bind_evidence_backed_actions(
    result: FactoredIntentResult, text: str
) -> FactoredIntentResult:
    """Replace generative actions with the deterministic evidence-backed action set."""

    return result.model_copy(update={"requested_actions": extract_requested_actions(text)})
