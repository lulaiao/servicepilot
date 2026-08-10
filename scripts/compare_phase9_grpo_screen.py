#!/usr/bin/env python3
"""Compare bounded GRPO output to its frozen executable SFT baseline."""

import argparse
import json
from pathlib import Path
from typing import Any

from servicepilot.training.advancement import AgentMetricSnapshot, assess_grpo_advancement


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def snapshot(payload: dict[str, Any]) -> AgentMetricSnapshot:
    agent = payload["learned_extractor_agent"]
    report = agent["report"]
    return AgentMetricSnapshot(
        task_success=report["executable_task_success_rate"],
        final_state_accuracy=report["final_state_accuracy"],
        policy_violation_rate=report["policy_violation_rate"],
        false_success_rate=report["false_success_rate"],
        unsafe_high_risk_error_rate=agent["risk"]["unsafe_high_risk_error_rate"],
        schema_valid_rate=agent["schema_valid_rate"],
        runtime_error_count=agent["runtime_error_count"],
    )


def main() -> None:
    args = parse_args()
    baseline = snapshot(json.loads(args.baseline.read_text(encoding="utf-8")))
    candidate = snapshot(json.loads(args.candidate.read_text(encoding="utf-8")))
    decision = assess_grpo_advancement(baseline, candidate)
    payload = {
        "baseline_report": str(args.baseline),
        "candidate_report": str(args.candidate),
        "baseline": baseline.model_dump(mode="json"),
        "candidate": candidate.model_dump(mode="json"),
        "decision": decision.model_dump(mode="json"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
