#!/usr/bin/env python3
"""Apply the frozen safety-first order to executable dev checkpoint reports."""

import argparse
import json
from pathlib import Path

from servicepilot.training import CheckpointEvidence, SeedRunState, select_checkpoint


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-report", type=Path, required=True)
    parser.add_argument("--harness-report", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    training = json.loads(args.training_report.read_text(encoding="utf-8"))
    state = SeedRunState.model_validate(training["run_state"])
    by_path = {item.path: item for item in state.checkpoints}
    evaluated: list[CheckpointEvidence] = []
    for report_path in args.harness_report:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("split") != "dev":
            raise RuntimeError(f"checkpoint selection requires dev evidence: {report_path}")
        checkpoint = str(report["checkpoint"])
        if checkpoint not in by_path:
            raise RuntimeError(f"unknown checkpoint in harness report: {checkpoint}")
        metrics = report.get("checkpoint_selection_metrics", report)
        evaluated.append(
            by_path[checkpoint].model_copy(
                update={
                    "executable_task_success": float(metrics["executable_task_success"]),
                    "high_risk_error_rate": float(metrics["high_risk_error_rate"]),
                }
            )
        )
    if len(evaluated) != len(by_path):
        raise RuntimeError("every saved checkpoint must have executable dev evidence")
    selected = select_checkpoint(tuple(evaluated))
    selected_state = state.model_copy(
        update={
            "status": "selected",
            "checkpoints": tuple(evaluated),
            "selected_checkpoint": selected.path,
        }
    )
    payload = {
        "selection_split": "dev",
        "selection_order": [
            "zero_high_risk_error",
            "highest_executable_dev_task_success",
            "lowest_dev_loss",
        ],
        "run_state": selected_state.model_dump(mode="json"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
