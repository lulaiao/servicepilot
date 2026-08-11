#!/usr/bin/env python3
"""CPU replay of composition binding over immutable classifier records."""

import argparse
import hashlib
import json
from pathlib import Path

from servicepilot.eval.models import Intent, ScenarioSpec
from servicepilot.routing.composition_evidence import bind_composition_evidence
from servicepilot.routing.models import IntentResult
from servicepilot.training.classifier_data import classifier_target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.report.read_text(encoding="utf-8"))
    records = source["learned_extractor_agent"]["classifier_records"]
    scenarios = tuple(
        ScenarioSpec.model_validate_json(line)
        for line in args.catalog.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len(records) != len(scenarios):
        raise RuntimeError("record and scenario counts differ")

    changed = []
    before_correct = after_correct = rescue = harm = 0
    for scenario, record in zip(scenarios, records, strict=True):
        before = IntentResult.model_validate(record["prediction"])
        after = bind_composition_evidence(before, scenario.user_utterance)
        gold = classifier_target(scenario)
        expected = (gold.primary_intent, *gold.secondary_intents)
        before_tuple = (before.primary_intent, *before.secondary_intents)
        after_tuple = (after.primary_intent, *after.secondary_intents)
        was_correct = before_tuple == expected
        is_correct = after_tuple == expected
        before_correct += was_correct
        after_correct += is_correct
        rescue += not was_correct and is_correct
        harm += was_correct and not is_correct
        if before_tuple != after_tuple:
            changed.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "before": [item.value for item in before_tuple],
                    "after": [item.value for item in after_tuple],
                    "expected": [item.value for item in expected],
                    "effect": "rescue" if not was_correct and is_correct else "harm" if was_correct else "neutral",
                }
            )
    count = len(scenarios)
    payload = {
        "schema_version": "servicepilot-composition-binding-replay-v1",
        "source_report": str(args.report),
        "source_report_sha256": hashlib.sha256(args.report.read_bytes()).hexdigest(),
        "catalog": str(args.catalog),
        "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        "scenario_count": count,
        "before_exact_rate": round(before_correct / count, 4),
        "after_exact_rate": round(after_correct / count, 4),
        "changed_count": len(changed),
        "rescue_count": rescue,
        "harm_count": harm,
        "records": changed,
        "claim_scope": "reused_dev_cpu_diagnostic_only",
        "sealed_accessed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
