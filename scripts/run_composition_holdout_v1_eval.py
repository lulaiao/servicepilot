#!/usr/bin/env python3
"""One-shot evaluation of no-binding versus frozen composition binding."""

import argparse
import hashlib
import json
from pathlib import Path

from servicepilot.eval.composition_holdout_v1 import CompositionHoldoutCase
from servicepilot.eval.models import Intent
from servicepilot.routing.composition_evidence import bind_composition_evidence
from servicepilot.routing.models import IntentResult, RiskLevel

TARGET = (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("one-shot output already exists; rerun is forbidden")
    cases = tuple(
        CompositionHoldoutCase.model_validate_json(line)
        for line in args.catalog.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
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
        baseline_bound = (before.primary_intent, *before.secondary_intents) == TARGET
        binder_bound = (after.primary_intent, *after.secondary_intents) == TARGET
        records.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "should_bind": case.should_bind,
                "baseline_bound": baseline_bound,
                "binder_bound": binder_bound,
                "baseline_success": baseline_bound == case.should_bind,
                "binder_success": binder_bound == case.should_bind,
            }
        )
    count = len(records)

    def metrics(key: str) -> dict[str, float | int | str]:
        bound_key = f"{key}_bound"
        success_key = f"{key}_success"
        false_bindings = sum(item[bound_key] and not item["should_bind"] for item in records)
        missed_bindings = sum(not item[bound_key] and item["should_bind"] for item in records)
        return {
            "task_success_rate": round(sum(item[success_key] for item in records) / count, 4),
            "false_binding_rate": round(false_bindings / count, 4),
            "missed_binding_rate": round(missed_bindings / count, 4),
            "legitimate_secondary_action_count": sum(
                item[bound_key] and item["should_bind"] for item in records
            ),
            "unexpected_secondary_action_count": false_bindings,
            "false_success_rate": "TBD_not_executable_agent_scenarios",
        }

    payload = {
        "schema_version": "servicepilot-composition-holdout-v1-result",
        "code_revision": args.code_revision,
        "catalog": str(args.catalog),
        "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        "case_count": count,
        "baseline": metrics("baseline"),
        "composition_binder": metrics("binder"),
        "changed_count": sum(item["baseline_bound"] != item["binder_bound"] for item in records),
        "records": records,
        "claim_scope": "composition_binding_functional_holdout",
        "model_inference_executed": False,
        "executable_agent_false_success_measured": False,
        "selection_or_tuning_allowed": False,
        "rerun_allowed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: value for key, value in payload.items() if key != "records"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
