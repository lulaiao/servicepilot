#!/usr/bin/env python3
"""Replay recorded classifier outputs through the current executable Agent Harness."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.models import ScenarioSpec
from servicepilot.eval.runner import build_report, run_scenario
from servicepilot.routing.models import IntentResult


class RecordedClassifier:
    def __init__(self, predictions: dict[str, IntentResult]) -> None:
        self.predictions = predictions

    def classify(self, text: str) -> IntentResult:
        try:
            return self.predictions[text]
        except KeyError as exc:
            raise RuntimeError("recorded classifier has no prediction for text") from exc


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.report.read_text(encoding="utf-8"))
    records = source["learned_extractor_agent"]["classifier_records"]
    predictions = {
        item["text"]: IntentResult.model_validate(item["prediction"]) for item in records
    }
    scenarios = tuple(
        ScenarioSpec.model_validate_json(line)
        for line in args.catalog.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len(predictions) != len(scenarios):
        raise RuntimeError("recorded predictions and scenarios differ")

    results = []
    composition_binding_count = 0
    for scenario in scenarios:
        agent = RoutedRuleAgent(
            classifier=RecordedClassifier(predictions), composition_binding=True
        )
        _, result, _ = await run_scenario(scenario, agent=agent)
        results.append(result)
        composition_binding_count += agent.composition_binding_count
    report = build_report(scenarios, results)
    payload = {
        "schema_version": "servicepilot-recorded-agent-composition-replay-v1",
        "source_report": str(args.report),
        "source_report_sha256": hashlib.sha256(args.report.read_bytes()).hexdigest(),
        "catalog": str(args.catalog),
        "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        "report": report.model_dump(mode="json"),
        "composition_binding_count": composition_binding_count,
        "claim_scope": "reused_dev_recorded_output_deterministic_harness_replay",
        "model_inference_executed": False,
        "sealed_accessed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
