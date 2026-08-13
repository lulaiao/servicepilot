"""Ordered Harness guardrail pipeline."""

from servicepilot.harness.models import (
    GuardrailDecision,
    GuardrailStage,
)
from servicepilot.harness.protocols import Guardrail


class PromptInjectionInputGuardrail:
    name = "prompt_injection_input_guardrail"

    def evaluate(self, stage: GuardrailStage, payload: dict[str, object]) -> GuardrailDecision:
        text = str(payload.get("text", ""))
        blocked = stage is GuardrailStage.INPUT and any(
            marker in text for marker in ("忽略规则", "直接修改数据库")
        )
        return GuardrailDecision(
            allowed=not blocked,
            guardrail=self.name,
            reason=(
                "policy-bypass pattern detected" if blocked else "no policy-bypass pattern detected"
            ),
        )


class GuardrailPipeline:
    def __init__(self, guardrails: tuple[Guardrail, ...] = ()) -> None:
        self.guardrails = guardrails

    def evaluate(
        self, stage: GuardrailStage, payload: dict[str, object]
    ) -> tuple[GuardrailDecision, ...]:
        decisions: list[GuardrailDecision] = []
        for guardrail in self.guardrails:
            decision = guardrail.evaluate(stage, payload)
            decisions.append(decision)
            if not decision.allowed:
                break
        return tuple(decisions)

    @staticmethod
    def allowed(decisions: tuple[GuardrailDecision, ...]) -> bool:
        return all(item.allowed for item in decisions)
