"""Rule-first issue extraction with evidence and explicit abstention."""

import re
from dataclasses import dataclass

from servicepilot.routing.action_evidence import extract_requested_actions
from servicepilot.routing.factored_intent import FactoredIntentResult, IssueType


@dataclass(frozen=True)
class IssueEvidence:
    issue_type: IssueType
    text: str
    start: int
    end: int
    reason: str


_ISSUE_PATTERNS: tuple[tuple[IssueType, tuple[re.Pattern[str], ...]], ...] = (
    (
        IssueType.MISSING_OR_WRONG_ITEM,
        (
            re.compile(r"(?:少送|漏发|缺少|未送来|没有送来|错货|装错|错误型号)"),
            re.compile(r"(?:包裹内容|配送内容).{0,8}(?:不全|不符)"),
            re.compile(r"(?:收到|货品).{0,8}(?:错误|不是下单)"),
        ),
    ),
    (
        IssueType.DUPLICATE_CHARGE,
        (
            re.compile(r"(?:重复扣费|重复收费|重复记账|重复入账|额外扣款|再次扣款)"),
            re.compile(r"(?:扣了两次|扣款两遍|收了两次|多记一笔|两笔相同收费)"),
        ),
    ),
    (
        IssueType.COUPON_ISSUE,
        (
            re.compile(
                r"(?:优惠券|抵扣券|优惠码|折扣券).{0,14}(?:没有恢复|不可用|已核销|无法|不正确)"
            ),
            re.compile(
                r"(?:没有恢复|不可用|已核销|无法生效|状态不正确).{0,10}(?:优惠券|抵扣券|优惠码|折扣券)"
            ),
            re.compile(r"券状态.{0,8}不正确"),
        ),
    ),
    (
        IssueType.DELIVERY_DELAY,
        (
            re.compile(
                r"(?:配送|送达|履约|物流|运输).{0,12}(?:延误|逾期|超期|超时|迟滞|停滞|没到|未完成|没有变化)"
            ),
            re.compile(
                r"(?:超过承诺|晚于预计|预定送达节点过去).{0,12}(?:未送达|尚未完成|还在途中)?"
            ),
            re.compile(r"一直没到"),
        ),
    ),
)
_DOMAIN_MARKERS = re.compile(
    r"(?:订单|购买|交易|商品|包裹|配送|送达|履约|物流|支付|扣款|收费|退款|"
    r"优惠券|抵扣券|优惠码|折扣券|客服|投诉|预约)"
)


def extract_issue_evidence(text: str) -> IssueEvidence | None:
    """Return a supported issue, deterministic none/OOS, or abstain for ambiguous domain text."""

    for issue_type, patterns in _ISSUE_PATTERNS:
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return IssueEvidence(
                    issue_type=issue_type,
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    reason="explicit_issue_pattern",
                )
    if extract_requested_actions(text):
        return IssueEvidence(IssueType.NONE, "", 0, 0, "explicit_action_without_issue")
    if not _DOMAIN_MARKERS.search(text):
        return IssueEvidence(IssueType.OUT_OF_SCOPE, "", 0, 0, "no_service_domain_signal")
    return None


def bind_rule_first_issue(result: FactoredIntentResult, text: str) -> FactoredIntentResult:
    evidence = extract_issue_evidence(text)
    if evidence is None:
        return result
    return result.model_copy(update={"issue_type": evidence.issue_type})
