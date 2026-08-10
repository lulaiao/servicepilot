#!/usr/bin/env python3
"""Replay a factored model report with deterministic evidence-backed actions."""

import argparse
import hashlib
import json
from pathlib import Path

from servicepilot.eval.factored_metrics import factored_metrics
from servicepilot.routing.action_evidence import (
    bind_evidence_backed_actions,
    extract_requested_action_evidence,
)
from servicepilot.routing.factored_intent import FactoredIntentResult
from servicepilot.training.data_models import SFTTrainingRecord


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source = json.loads(args.report.read_text(encoding="utf-8"))
    dataset = {
        item.record_id: item
        for item in (
            SFTTrainingRecord.model_validate_json(line)
            for line in args.dataset.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    targets = []
    predictions = []
    records = []
    for record in source["records"]:
        example_id = record["example_id"]
        if example_id not in dataset:
            raise RuntimeError(f"report example missing from dataset: {example_id}")
        item = dataset[example_id]
        text = item.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1]
        target = FactoredIntentResult.model_validate(record["gold"])
        raw_prediction = (
            FactoredIntentResult.model_validate(record["prediction"])
            if record["prediction"] is not None
            else None
        )
        bound = bind_evidence_backed_actions(raw_prediction, text) if raw_prediction else None
        evidence = extract_requested_action_evidence(text)
        targets.append(target)
        predictions.append(bound)
        records.append(
            {
                "example_id": example_id,
                "text": text,
                "gold": target.model_dump(mode="json"),
                "raw_prediction": raw_prediction.model_dump(mode="json") if raw_prediction else None,
                "bound_prediction": bound.model_dump(mode="json") if bound else None,
                "action_evidence": [
                    {
                        "action": value.action.value,
                        "text": value.text,
                        "start": value.start,
                        "end": value.end,
                    }
                    for value in evidence
                ],
                "raw_actions_changed": (
                    raw_prediction is not None
                    and raw_prediction.requested_actions != bound.requested_actions
                ),
                "issue_action_exact": (
                    bound is not None
                    and bound.issue_type is target.issue_type
                    and set(bound.requested_actions) == set(target.requested_actions)
                ),
            }
        )
    metrics = factored_metrics(targets, predictions)
    payload = {
        "schema_version": "servicepilot-factored-action-binding-replay-v1",
        "source_report": str(args.report),
        "source_report_sha256": sha256(args.report),
        "dataset": str(args.dataset),
        "dataset_sha256": sha256(args.dataset),
        "binding": "deterministic_explicit_action_evidence_v1",
        **metrics,
        "changed_prediction_count": sum(item["raw_actions_changed"] for item in records),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in payload.items() if key != "records"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
