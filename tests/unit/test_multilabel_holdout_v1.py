from collections import Counter

from servicepilot.eval.models import Intent
from servicepilot.eval.multilabel_holdout_v1 import build_multilabel_holdout_v1
from servicepilot.training.multilabel_composition_data import build_multilabel_composition_v1


def test_multilabel_holdout_shape_labels_and_uniqueness() -> None:
    cases = build_multilabel_holdout_v1()

    assert len(cases) == 80
    assert len({case.case_id for case in cases}) == 80
    assert len({case.text for case in cases}) == 80
    assert {case.split for case in cases} == {"sealed_test"}
    assert Counter(case.category for case in cases) == {
        "explicit_pair": 10,
        "three_intent": 10,
        "delivery_only": 10,
        "negated_escalation": 10,
        "conditional_or_historical": 10,
        "complaint_only": 10,
        "refund_only": 10,
        "delivery_refund": 10,
    }
    assert Counter(label for case in cases for label in case.labels) == {
        Intent.DELIVERY_DELAY: 60,
        Intent.COMPLAINT_ESCALATION: 30,
        Intent.PARTIAL_REFUND: 30,
    }


def test_multilabel_holdout_has_no_exact_training_text_or_signature_overlap() -> None:
    holdout = build_multilabel_holdout_v1()
    training = build_multilabel_composition_v1()

    assert not {case.text for case in holdout} & {item.text for item in training}
    assert not {case.semantic_signature_sha256 for case in holdout} & {
        item.semantic_signature_sha256 for item in training
    }
