import json
from pathlib import Path

import pytest

from servicepilot.training import SFTExperimentProtocol

PROTOCOL = Path("experiments/configs/phase9_qwen25_7b_lora_sft_v1.json")


def test_frozen_sft_protocol_passes_safety_and_reproducibility_gates() -> None:
    protocol = SFTExperimentProtocol.model_validate_json(PROTOCOL.read_text())

    assert len(protocol.seeds) == 4
    assert not protocol.sealed_used_for_selection
    assert protocol.checkpoint_selection[0] == "zero_high_risk_error"
    assert protocol.budget.max_epochs == 3


def test_protocol_rejects_sealed_selection_and_insufficient_seeds() -> None:
    raw = json.loads(PROTOCOL.read_text())
    raw.update({"seeds": [1, 2], "sealed_used_for_selection": True})

    with pytest.raises(ValueError):
        SFTExperimentProtocol.model_validate(raw)


def test_protocol_screening_must_use_a_formal_seed() -> None:
    raw = json.loads(PROTOCOL.read_text())
    raw.update({"screening_seed": 7, "screening_max_steps": 25})

    with pytest.raises(ValueError, match="screening seed"):
        SFTExperimentProtocol.model_validate(raw)


def test_versioned_harness_requires_override_metrics() -> None:
    raw = json.loads(PROTOCOL.read_text())
    raw["harness_revision"] = "abc123"

    with pytest.raises(ValueError, match="override metrics"):
        SFTExperimentProtocol.model_validate(raw)


def test_protocol_allows_explicitly_deferred_sealed_catalog() -> None:
    raw = json.loads(PROTOCOL.read_text())
    raw["split_counts"]["sealed_test"] = 0
    raw["sealed_execution"] = "deferred_until_independent_catalog_freeze"

    protocol = SFTExperimentProtocol.model_validate(raw)

    assert protocol.split_counts["sealed_test"] == 0


def test_protocol_rejects_implicit_missing_sealed_catalog() -> None:
    raw = json.loads(PROTOCOL.read_text())
    raw["split_counts"]["sealed_test"] = 0

    with pytest.raises(ValueError, match="explicitly deferred"):
        SFTExperimentProtocol.model_validate(raw)


def test_protocol_accepts_decomposed_safety_as_first_gate() -> None:
    raw = json.loads(PROTOCOL.read_text())
    raw["checkpoint_selection"][0] = "zero_unauthorized_action"

    protocol = SFTExperimentProtocol.model_validate(raw)

    assert protocol.checkpoint_selection[0] == "zero_unauthorized_action"
