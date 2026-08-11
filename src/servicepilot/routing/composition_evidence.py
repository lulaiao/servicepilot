"""Evidence-gated composition of independent executable intents."""

import re
from dataclasses import dataclass

from servicepilot.eval.models import Intent
from servicepilot.routing.models import IntentResult, RiskLevel


@dataclass(frozen=True)
class CompositionEvidence:
    primary_intent: Intent
    secondary_intent: Intent
    delivery_span: str
    escalation_span: str


_DELIVERY = re.compile(
    r"(?:配送|送达|履约|运输|物流|骑手|商品).{0,12}"
    r"(?:延迟|延误|超时|超期|逾期|迟滞|异常|停滞|没到|没有送到|没有完成|未完成|超过|晚于)"
    r"|(?:延迟|延误|超时|超期|逾期|迟滞).{0,6}(?:配送|送达|履约|运输|物流)?"
)
_ESCALATION = re.compile(
    r"(?:人工投诉|正式投诉|投诉处理|转人工|人工处理|人工介入|客服升级|升级请求|"
    r"专员接手|专员介入|建立.{0,4}工单|创建.{0,4}工单)"
)
_NEGATION = re.compile(r"(?:不|不要|不用|无需|别|暂不|先不|没有要求|只.{0,4}不)")
_CONDITIONAL = re.compile(r"(?:如果|若|要是).{0,20}(?:再|才)")
_HISTORICAL = re.compile(
    r"(?:上次|此前|之前|曾经).{0,18}(?:投诉|转.{0,2}人工|升级)"
    r"|已经(?:投诉|转过人工|升级过)"
)


def _positive_match(pattern: re.Pattern[str], text: str) -> re.Match[str] | None:
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 8) : match.start()]
        if not _NEGATION.search(prefix):
            return match
    return None


def extract_composition_evidence(text: str) -> CompositionEvidence | None:
    """Require explicit positive evidence for both independent actions."""

    if _CONDITIONAL.search(text) or _HISTORICAL.search(text):
        return None
    delivery = _positive_match(_DELIVERY, text)
    escalation = _positive_match(_ESCALATION, text)
    if delivery is None or escalation is None:
        return None
    return CompositionEvidence(
        primary_intent=Intent.DELIVERY_DELAY,
        secondary_intent=Intent.COMPLAINT_ESCALATION,
        delivery_span=delivery.group(0),
        escalation_span=escalation.group(0),
    )


def bind_composition_evidence(result: IntentResult, text: str) -> IntentResult:
    """Bind a supported delivery+escalation pair without inventing other intents."""

    evidence = extract_composition_evidence(text)
    if evidence is None:
        return result
    current = (result.primary_intent, *result.secondary_intents)
    expected = (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION)
    if current == expected:
        return result
    supported = {Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION}
    if not (supported & set(current)) or not set(current) <= supported:
        return result
    return result.model_copy(
        update={
            "primary_intent": evidence.primary_intent,
            "secondary_intents": (evidence.secondary_intent,),
            "risk_level": RiskLevel.MEDIUM,
        }
    )
