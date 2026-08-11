from collections import Counter

from servicepilot.eval.composition_adversarial import build_composition_adversarial_v1
from servicepilot.eval.composition_holdout_v1 import build_composition_holdout_v1


def test_holdout_is_balanced_frozen_shape_and_unique() -> None:
    cases = build_composition_holdout_v1()

    assert len(cases) == 60
    assert len({item.case_id for item in cases}) == 60
    assert len(
        {(item.text, item.model_primary, item.model_secondary) for item in cases}
    ) == 60
    assert Counter(item.category for item in cases) == {
        "explicit_pair": 10,
        "negated_escalation": 10,
        "conditional_future": 10,
        "historical_request": 10,
        "existing_third_intent": 10,
        "unrelated_model_output": 10,
    }
    assert sum(item.should_bind for item in cases) == 10


def test_holdout_has_no_exact_text_and_state_overlap_with_adversarial_dev() -> None:
    holdout = {
        (item.text, item.model_primary, item.model_secondary)
        for item in build_composition_holdout_v1()
    }
    dev = {
        (item.text, item.model_primary, item.model_secondary)
        for item in build_composition_adversarial_v1()
    }

    assert not holdout & dev
