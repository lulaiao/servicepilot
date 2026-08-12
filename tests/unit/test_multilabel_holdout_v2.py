from collections import Counter

from servicepilot.eval.models import Intent
from servicepilot.eval.multilabel_holdout_v1 import build_multilabel_holdout_v1
from servicepilot.eval.multilabel_holdout_v2 import build_multilabel_holdout_v2
from servicepilot.training.multilabel_composition_v2_data import (
    build_multilabel_composition_v2,
)


def test_multilabel_holdout_v2_is_balanced_unique_and_sealed() -> None:
    cases = build_multilabel_holdout_v2()

    assert len(cases) == 64
    assert len({case.case_id for case in cases}) == 64
    assert len({case.text for case in cases}) == 64
    assert {case.split for case in cases} == {"sealed_test"}
    assert Counter(case.category for case in cases) == {
        f"label_set_{bits:03b}": 8 for bits in range(8)
    }
    assert Counter(label for case in cases for label in case.labels) == {
        Intent.DELIVERY_DELAY: 32,
        Intent.COMPLAINT_ESCALATION: 32,
        Intent.PARTIAL_REFUND: 32,
    }


def test_multilabel_holdout_v2_has_no_exact_text_overlap_with_prior_corpora() -> None:
    texts = {case.text for case in build_multilabel_holdout_v2()}
    assert not texts & {item.text for item in build_multilabel_composition_v2()}
    assert not texts & {item.text for item in build_multilabel_holdout_v1()}
