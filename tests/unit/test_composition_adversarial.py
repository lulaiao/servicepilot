from collections import Counter

from servicepilot.eval.composition_adversarial import build_composition_adversarial_v1
from servicepilot.eval.models import Intent
from servicepilot.routing.composition_evidence import bind_composition_evidence
from servicepilot.routing.models import IntentResult, RiskLevel


def test_composition_adversarial_v1_is_balanced_and_unique() -> None:
    cases = build_composition_adversarial_v1()
    counts = Counter(item.category for item in cases)

    assert len(cases) == 120
    assert len({item.case_id for item in cases}) == 120
    assert len({(item.text, item.model_primary, item.model_secondary) for item in cases}) == 120
    assert counts == {
        "explicit_pair": 32,
        "negated_escalation": 24,
        "conditional_future": 24,
        "historical_request": 16,
        "delivery_only": 8,
        "three_intent": 8,
        "escalation_only": 4,
        "unrelated_model_output": 4,
    }


def test_only_explicit_pairs_are_positive() -> None:
    cases = build_composition_adversarial_v1()

    assert sum(item.should_bind for item in cases) == 32
    assert all(item.should_bind == (item.category == "explicit_pair") for item in cases)


def test_binder_passes_adversarial_safety_contract() -> None:
    for case in build_composition_adversarial_v1():
        before = IntentResult(
            primary_intent=case.model_primary,
            secondary_intents=case.model_secondary,
            slots={"order_id": None, "reason": None, "requested_amount": None},
            risk_level=RiskLevel.MEDIUM,
            confidence=0.9,
            needs_clarification=True,
        )
        after = bind_composition_evidence(before, case.text)
        bound = (after.primary_intent, *after.secondary_intents) == (
            Intent.DELIVERY_DELAY,
            Intent.COMPLAINT_ESCALATION,
        )
        assert bound is case.should_bind, case.case_id
