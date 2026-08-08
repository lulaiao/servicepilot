"""Independent semantic-family contracts and the first sealed catalog."""

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict

from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.models import Intent, ScenarioSpec
from servicepilot.mcp_gateway.faults import FaultKind
from servicepilot.training.data_models import DataSplit


class ExpandedScenarioFamily(BaseModel):
    model_config = ConfigDict(frozen=True)

    family_id: str
    split: DataSplit
    provenance: str
    dimensions: dict[str, Any]
    semantic_signature_sha256: str
    canonical_scenario: ScenarioSpec


def _signature(dimensions: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(dimensions, sort_keys=True, default=str).encode()).hexdigest()


def build_phase9_sealed_families() -> tuple[ExpandedScenarioFamily, ...]:
    """Build 40 independently reserved families; never use them for tuning."""
    base_by_intent = {
        scenario.intent: scenario
        for scenario in build_phase3_scenarios()
        if scenario.scenario_id.endswith("-01")
    }
    recipes: list[tuple[Intent, str, FaultKind | None]] = []
    tool_intents = tuple(intent for intent in Intent if intent is not Intent.OUT_OF_SCOPE)
    recipes.extend((intent, "clean", None) for intent in Intent)
    recipes.extend((intent, "transient_retry", FaultKind.TRANSIENT) for intent in tool_intents)
    recipes.extend((intent, "timeout_retry", FaultKind.TIMEOUT) for intent in tool_intents)
    lost_response_intents = (
        Intent.CANCEL_ORDER,
        Intent.FULL_REFUND,
        Intent.PARTIAL_REFUND,
        Intent.MISSING_OR_WRONG_ITEM,
        Intent.COUPON_ISSUE,
        Intent.RESCHEDULE,
    )
    recipes.extend(
        (intent, "lost_response_recovery", FaultKind.LOST_RESPONSE)
        for intent in lost_response_intents
    )
    assert len(recipes) == 40
    families: list[ExpandedScenarioFamily] = []
    for intent, profile, fault in recipes:
        base = base_by_intent[intent]
        family_id = f"sealed-{intent.value}-{profile}"
        faults: dict[str, tuple[FaultKind, ...]] = {}
        fault_tool: str | None = None
        if fault is not None:
            fault_tool = (
                base.allowed_actions[-1]
                if fault is FaultKind.LOST_RESPONSE
                else base.allowed_actions[0]
            )
            faults[fault_tool] = (fault,)
        dimensions = {
            "intent": intent.value,
            "initial_order_status": base.initial_order_status.value,
            "requested_amount": str(base.requested_amount),
            "confirmation": "accept" if base.accept_confirmation else "reject",
            "fault_profile": profile,
            "fault_tool": fault_tool,
            "policy_version": "2026.1",
            "city": "Shanghai",
            "business_type": "food_delivery",
        }
        scenario = base.model_copy(
            update={
                "scenario_id": family_id,
                "order_id": family_id,
                "user_id": f"synthetic-user-{family_id}",
                "faults": faults,
            }
        )
        families.append(
            ExpandedScenarioFamily(
                family_id=family_id,
                split=DataSplit.SEALED_TEST,
                provenance="independently_authored_phase9_sealed_v1",
                dimensions=dimensions,
                semantic_signature_sha256=_signature(dimensions),
                canonical_scenario=scenario,
            )
        )
    return tuple(families)
