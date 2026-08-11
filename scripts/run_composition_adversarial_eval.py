#!/usr/bin/env python3
"""Evaluate composition binding on deterministic adversarial train/dev cases."""

import argparse
import json
from collections import Counter
from pathlib import Path

from servicepilot.eval.composition_adversarial import build_composition_adversarial_v1
from servicepilot.eval.models import Intent
from servicepilot.routing.composition_evidence import bind_composition_evidence
from servicepilot.routing.models import IntentResult, RiskLevel


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = build_composition_adversarial_v1()
    records = []
    for case in cases:
        before = IntentResult(
            primary_intent=case.model_primary,
            secondary_intents=case.model_secondary,
            slots={"order_id": None, "reason": None, "requested_amount": None},
            risk_level=RiskLevel.MEDIUM,
            confidence=0.9,
            needs_clarification=True,
        )
        after = bind_composition_evidence(before, case.text)
        expected_tuple = (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION)
        bound = (after.primary_intent, *after.secondary_intents) == expected_tuple
        records.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "should_bind": case.should_bind,
                "bound": bound,
                "passed": bound == case.should_bind,
            }
        )
    false_bindings = [item for item in records if item["bound"] and not item["should_bind"]]
    missed_bindings = [item for item in records if not item["bound"] and item["should_bind"]]
    counts = Counter(item.category for item in cases)
    payload = {
        "schema_version": "servicepilot-composition-adversarial-eval-v1",
        "case_count": len(cases),
        "category_counts": dict(sorted(counts.items())),
        "pass_count": sum(item["passed"] for item in records),
        "pass_rate": round(sum(item["passed"] for item in records) / len(records), 4),
        "false_binding_count": len(false_bindings),
        "missed_binding_count": len(missed_bindings),
        "false_bindings": false_bindings,
        "missed_bindings": missed_bindings,
        "claim_scope": "iterable_train_dev_safety_contract",
        "sealed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
