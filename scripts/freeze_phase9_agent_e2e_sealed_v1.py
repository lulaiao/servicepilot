#!/usr/bin/env python3
"""Freeze Agent sealed v1 after validating only the gold workflow."""

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.eval.agent_sealed_v1 import (
    CATALOG_VERSION,
    PROVENANCE,
    build_agent_e2e_sealed_v1,
    sealed_profile_counts,
)
from servicepilot.eval.hard_catalog import ScenarioGoldAgent
from servicepilot.eval.runner import run_scenario


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    scenarios = build_agent_e2e_sealed_v1()
    results = []
    for scenario in scenarios:
        _, judge, _ = await run_scenario(
            scenario, agent=ScenarioGoldAgent(scenario)
        )
        results.append(judge)
    if not all(item.task_success for item in results):
        failures = [item.model_dump(mode="json") for item in results if not item.task_success]
        raise RuntimeError(f"gold workflow execution gate failed: {failures}")

    encoded = "".join(item.model_dump_json() + "\n" for item in scenarios).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    intent_counts = Counter(item.intent.value for item in scenarios)
    payload = {
        "schema_version": CATALOG_VERSION,
        "provenance": PROVENANCE,
        "code_revision_before_freeze": args.code_revision,
        "catalog": str(args.output),
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "scenario_count": len(scenarios),
        "intent_counts": dict(sorted(intent_counts.items())),
        "profile_counts": sealed_profile_counts(scenarios),
        "gold_workflow_gate": {
            "executed_scenarios": len(results),
            "task_success_count": sum(item.task_success for item in results),
            "false_success_count": sum(item.false_success for item in results),
            "purpose": "fixture_and_judge_validation_only",
        },
        "candidate_models_executed": [],
        "selection_or_tuning_allowed": False,
        "one_shot_candidate": "phase9_classifier_sft_v5_checkpoint10",
        "one_shot_evaluation_executed": False,
        "rerun_allowed": False,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
