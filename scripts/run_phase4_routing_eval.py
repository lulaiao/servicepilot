#!/usr/bin/env python3
"""Evaluate routing components and single-vs-routed executable baselines."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.routing_dataset import DatasetSplit, build_routing_dataset
from servicepilot.eval.routing_metrics import evaluate_extractor
from servicepilot.eval.runner import run_suite
from servicepilot.routing.intent_rules import RuleIntentClassifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/phase4_routing_baselines.json"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("artifacts/reports/phase4_routing_manifest.json"),
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=Path("artifacts/traces/phase4_routed_trajectories.jsonl"),
    )
    parser.add_argument(
        "--include-sealed",
        action="store_true",
        help="Open the sealed split exactly once for a final evaluation.",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    examples = build_routing_dataset()
    scenarios = build_phase3_scenarios()
    classifier = RuleIntentClassifier()
    evaluated_splits = (
        tuple(DatasetSplit)
        if args.include_sealed
        else (DatasetSplit.TRAIN, DatasetSplit.DEV)
    )
    component = {
        split.value: evaluate_extractor(
            examples, classifier.classify, split
        ).model_dump(mode="json")
        for split in evaluated_splits
    }
    _, _, single_report = await run_suite(scenarios)
    routed_trajectories, _, routed_report = await run_suite(
        scenarios, agent_factory=RoutedRuleAgent
    )
    route_events = [
        event
        for trajectory in routed_trajectories
        for event in trajectory.events
        if event.kind in {"route", "reroute_after_observation"}
    ]
    payload: dict[str, Any] = {
        "intent_slot_component": component,
        "executable_comparison": {
            "shared_conditions": {
                "scenario_count": len(scenarios),
                "tool_budget_per_scenario": 12,
                "gateway_retry_budget": 2,
                "judge": "deterministic",
                "business_policy": "shared RuleBasedSingleAgent implementation",
            },
            "single_agent": single_report.model_dump(mode="json"),
            "dynamic_multi_role": routed_report.model_dump(mode="json"),
            "routing_event_count": len(route_events),
            "mean_routing_events_per_scenario": round(
                len(route_events) / len(scenarios), 3
            ),
        },
    }
    dataset_bytes = b"\n".join(
        item.model_dump_json().encode() for item in examples
    )
    scenario_bytes = b"\n".join(
        item.model_dump_json().encode() for item in scenarios
    )
    manifest = {
        "routing_example_count": len(examples),
        "routing_dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "scenario_count": len(scenarios),
        "scenario_sha256": hashlib.sha256(scenario_bytes).hexdigest(),
        "seed": 20260805,
        "sealed_test_used_for_selection": False,
        "sealed_test_evaluated": args.include_sealed,
        "output": str(args.output),
        "trace_output": str(args.trace_output),
    }
    for path in (args.output, args.manifest_output, args.trace_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    args.trace_output.write_text(
        "\n".join(item.model_dump_json() for item in routed_trajectories) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
