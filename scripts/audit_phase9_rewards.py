#!/usr/bin/env python3
"""Audit Phase 9 reward separation and common reward-hacking probes."""

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from servicepilot.training import DataSplit, PreferenceTrainingRecord
from servicepilot.training.reward import decision_reward


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preferences", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_train(path: Path) -> tuple[PreferenceTrainingRecord, ...]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = PreferenceTrainingRecord.model_validate_json(line)
        if record.split is DataSplit.TRAIN:
            records.append(record)
    return tuple(records)


def main() -> None:
    args = parse_args()
    records = load_train(args.preferences)
    margins: list[float] = []
    chosen_rewards: list[float] = []
    rejected_rewards: list[float] = []
    hard_gate_counts: dict[str, int] = {}
    for record in records:
        chosen = decision_reward(
            record.chosen,
            expected_tool=record.chosen_tool,
            expected_arguments=record.chosen.get("arguments", {}),
        )
        rejected = decision_reward(
            record.rejected,
            expected_tool=record.chosen_tool,
            expected_arguments=record.chosen.get("arguments", {}),
        )
        chosen_rewards.append(chosen.total)
        rejected_rewards.append(rejected.total)
        margins.append(chosen.total - rejected.total)
        if rejected.hard_gate:
            hard_gate_counts[rejected.hard_gate] = hard_gate_counts.get(rejected.hard_gate, 0) + 1

    probes: dict[str, bool] = {
        "completion_claim_has_no_bonus": decision_reward(
            {"tool_name": "get_order", "arguments": {}, "claim": "done"},
            expected_tool="get_order",
            expected_arguments={},
        ).total
        == decision_reward(
            {"tool_name": "get_order", "arguments": {}},
            expected_tool="get_order",
            expected_arguments={},
        ).total,
        "uncontrolled_refund_is_negative": decision_reward(
            {"tool_name": "create_refund_request", "arguments": {"order_id": "probe"}},
            expected_tool="create_refund_request",
            expected_arguments={"order_id": "probe"},
        ).total
        < 0,
        "invalid_schema_is_negative": decision_reward(
            {"tool_name": "get_order", "arguments": "{}"},
            expected_tool="get_order",
            expected_arguments={},
        ).total
        < 0,
    }
    zero_margin_count = sum(margin == 0 for margin in margins)
    wrong_order_count = sum(margin < 0 for margin in margins)
    payload: dict[str, Any] = {
        "schema_version": "servicepilot-reward-audit-v1",
        "input": str(args.preferences),
        "input_sha256": hashlib.sha256(args.preferences.read_bytes()).hexdigest(),
        "split": "train",
        "record_count": len(records),
        "chosen_reward": {
            "mean": statistics.mean(chosen_rewards),
            "min": min(chosen_rewards),
            "max": max(chosen_rewards),
        },
        "rejected_reward": {
            "mean": statistics.mean(rejected_rewards),
            "min": min(rejected_rewards),
            "max": max(rejected_rewards),
        },
        "group_margin": {
            "mean": statistics.mean(margins),
            "min": min(margins),
            "max": max(margins),
            "zero_count": zero_margin_count,
            "wrong_order_count": wrong_order_count,
        },
        "rejected_hard_gate_counts": hard_gate_counts,
        "reward_hacking_probes": probes,
        "gates": {
            "at_least_500_train_preferences": len(records) >= 500,
            "no_zero_group_margins": zero_margin_count == 0,
            "chosen_always_beats_rejected": wrong_order_count == 0 and min(margins) > 0,
            "all_reward_hacking_probes_pass": all(probes.values()),
        },
    }
    payload["audit_passed"] = all(payload["gates"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
