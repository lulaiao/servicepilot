from servicepilot.eval.factored_holdout_v1 import CASES, build_factored_holdout_v1
from servicepilot.routing.factored_intent import FactoredIntentResult
from servicepilot.training.data_models import DataSplit


def test_holdout_is_sealed_typed_and_unique() -> None:
    records = build_factored_holdout_v1()

    assert len(CASES) == len(records) == 24
    assert all(item.split is DataSplit.SEALED_TEST for item in records)
    assert len({item.record_id for item in records}) == len(records)
    assert all(
        FactoredIntentResult.model_validate_json(item.messages[1]["content"]) for item in records
    )
