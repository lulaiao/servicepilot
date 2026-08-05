"""Transparent intent/slot baseline with confidence and injection handling."""

import re

from servicepilot.eval.models import Intent
from servicepilot.routing.models import IntentResult, RiskLevel

ORDER_PATTERN = re.compile(r"(phase3-[a-z_]+-\d{2}|ord-\d+)")
AMOUNT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:元|块)")


class RuleIntentClassifier:
    def classify(self, text: str) -> IntentResult:
        normalized = text.strip().lower()
        injection = any(
            phrase in normalized
            for phrase in ("忽略规则", "绕过政策", "直接修改数据库", "调用写工具")
        )
        slots: dict[str, str | None] = {
            "order_id": self._match(ORDER_PATTERN, normalized),
            "reason": None,
            "requested_amount": None,
        }
        if injection:
            return IntentResult(
                primary_intent=Intent.OUT_OF_SCOPE,
                slots=slots,
                risk_level=RiskLevel.HIGH,
                confidence=0.99,
                needs_clarification=False,
                injection_detected=True,
            )

        intents: list[Intent] = []
        if "优惠券" in normalized or "券还" in normalized:
            intents.append(Intent.COUPON_ISSUE)
        elif (
            "取消" in normalized
            or "不要了" in normalized
            or "刚下的单退掉" in normalized
        ):
            intents.append(Intent.CANCEL_ORDER)
        if any(token in normalized for token in ("慢", "延迟", "超时")):
            intents.append(Intent.DELIVERY_DELAY)
        if any(token in normalized for token in ("投诉", "人工", "工单")):
            intents.append(Intent.COMPLAINT_ESCALATION)
        if any(
            token in normalized
            for token in ("重复扣", "扣了两次", "扣了我两次", "重复收费")
        ):
            intents.append(Intent.DUPLICATE_CHARGE)
            slots["reason"] = "duplicate_charge"
        elif any(token in normalized for token in ("少了", "漏送", "错件", "不对")):
            intents.append(Intent.MISSING_OR_WRONG_ITEM)
            slots["reason"] = "missing_item"
        elif any(token in normalized for token in ("全额退款", "全部退", "整单退款")):
            intents.append(Intent.FULL_REFUND)
            slots["reason"] = "quality_issue"
        elif any(token in normalized for token in ("部分退款", "退我", "退12")):
            intents.append(Intent.PARTIAL_REFUND)
            slots["reason"] = "quality_issue"
        if any(
            token in normalized
            for token in ("改期", "修改预约", "改配送", "改到", "改一下")
        ):
            intents.append(Intent.RESCHEDULE)
        if any(token in normalized for token in ("订单状态", "到哪", "进度", "没消息")):
            intents.append(Intent.ORDER_QUERY)

        intents = list(dict.fromkeys(intents))
        if not intents:
            intents = [Intent.OUT_OF_SCOPE]
        amount = self._match(AMOUNT_PATTERN, normalized)
        if amount and any(
            intent
            in {
                Intent.FULL_REFUND,
                Intent.PARTIAL_REFUND,
                Intent.MISSING_OR_WRONG_ITEM,
                Intent.DUPLICATE_CHARGE,
            }
            for intent in intents
        ):
            slots["requested_amount"] = amount

        primary = intents[0]
        secondary = tuple(intents[1:])
        risk = (
            RiskLevel.HIGH
            if primary
            in {
                Intent.CANCEL_ORDER,
                Intent.FULL_REFUND,
                Intent.PARTIAL_REFUND,
                Intent.MISSING_OR_WRONG_ITEM,
                Intent.DUPLICATE_CHARGE,
                Intent.RESCHEDULE,
            }
            else RiskLevel.MEDIUM
            if primary
            in {
                Intent.DELIVERY_DELAY,
                Intent.COMPLAINT_ESCALATION,
                Intent.COUPON_ISSUE,
            }
            else RiskLevel.LOW
        )
        required_order = primary is not Intent.OUT_OF_SCOPE
        confidence = 0.96 if len(intents) == 1 else 0.9
        return IntentResult(
            primary_intent=primary,
            secondary_intents=secondary,
            slots=slots,
            risk_level=risk,
            confidence=confidence,
            needs_clarification=required_order and slots["order_id"] is None,
        )

    @staticmethod
    def _match(pattern: re.Pattern[str], text: str) -> str | None:
        match = pattern.search(text)
        return match.group(1) if match else None
