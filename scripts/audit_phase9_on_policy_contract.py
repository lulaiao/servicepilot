#!/usr/bin/env python3
"""Validate executable classifier rewards before a GRPO smoke run."""

import argparse
import json
import statistics
from pathlib import Path

from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.training.on_policy import (
    ExecutableClassifierReward,
    gold_completion,
    model_owned_scenarios,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    all_scenarios = build_phase3_scenarios()
    scenarios = model_owned_scenarios(all_scenarios)
    adapter = ExecutableClassifierReward(scenarios)
    rows = []
    for index, scenario in enumerate(scenarios):
        gold = adapter.score(gold_completion(scenario), scenario.scenario_id)
        invalid = adapter.score("任务已经完成", scenario.scenario_id)
        confusable = adapter.score(
            gold_completion(scenarios[(index + 3) % len(scenarios)]),
            scenario.scenario_id,
        )
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "gold_reward": gold.reward.total,
                "invalid_reward": invalid.reward.total,
                "confusable_reward": confusable.reward.total,
                "invalid_margin": gold.reward.total - invalid.reward.total,
                "confusable_margin": gold.reward.total - confusable.reward.total,
                "gold_task_success": gold.task_success,
                "confusable_guardrail_rescue": confusable.guardrail_rescue,
            }
        )
    margins = [row["confusable_margin"] for row in rows]
    payload = {
        "schema_version": "servicepilot-on-policy-contract-audit-v1",
        "scenario_count": len(scenarios),
        "guardrail_owned_excluded_count": len(all_scenarios) - len(scenarios),
        "execution_count": len(adapter.evidence),
        "prompt_contract": "deployed_intent_slot_classifier",
        "reward_source": "RoutedRuleAgent+tools+DeterministicJudge",
        "gold_task_success_count": sum(row["gold_task_success"] for row in rows),
        "guardrail_rescue_probe_count": sum(
            row["confusable_guardrail_rescue"] for row in rows
        ),
        "margin": {
            "mean": statistics.mean(margins),
            "min": min(margins),
            "zero_count": sum(margin == 0 for margin in margins),
            "negative_count": sum(margin < 0 for margin in margins),
        },
        "rows": rows,
    }
    payload["contract_validated"] = (
        payload["gold_task_success_count"] == len(scenarios)
        and payload["margin"]["min"] > 0
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
