"""Ordered Harness guardrail pipeline."""

from servicepilot.harness.models import (
    GuardrailDecision,
    GuardrailStage,
)
from servicepilot.harness.protocols import Guardrail


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

