#!/usr/bin/env python3
"""Calibrate deterministic Monitor precision/recall on frozen synthetic cases."""

import argparse
import hashlib
import json
from pathlib import Path

from servicepilot.monitoring import (
    DeterministicMonitor,
    MonitorFaultClass,
    MonitorObservation,
    MonitorScope,
)

CASES: tuple[tuple[str, dict[str, object], MonitorFaultClass | None], ...] = (
    (
        "false-success",
        {"claimed_success": True, "final_state_correct": False},
        MonitorFaultClass.FALSE_SUCCESS,
    ),
    ("policy", {"policy_compliant": False}, MonitorFaultClass.POLICY_VIOLATION),
    ("forbidden", {"forbidden_action_seen": True}, MonitorFaultClass.FORBIDDEN_ACTION),
    ("evidence", {"missing_evidence": True}, MonitorFaultClass.MISSING_EVIDENCE),
    (
        "budget",
        {"termination_reason": "tool_budget_exhausted"},
        MonitorFaultClass.BUDGET_EXHAUSTION,
    ),
    ("retry", {"retries_used": 3, "max_retries": 2}, MonitorFaultClass.RETRY_STORM),
    ("tool", {"tool_error_codes": ("TIMEOUT",)}, MonitorFaultClass.TOOL_FAILURE),
    ("duplicate", {"write_operation_ids": ("w1", "w1")}, MonitorFaultClass.DUPLICATE_WRITE),
    (
        "lost-response",
        {"committed_response_lost": True, "recovery_idempotent": False},
        MonitorFaultClass.UNSAFE_LOST_RESPONSE_RECOVERY,
    ),
    ("version", {"version_conflict_count": 1}, MonitorFaultClass.VERSION_CONFLICT),
    ("injection", {"prompt_injection_detected": True}, MonitorFaultClass.PROMPT_INJECTION),
    ("memory", {"memory_conflict_unresolved": True}, MonitorFaultClass.MEMORY_CONFLICT),
    (
        "confirmation",
        {"high_risk_write_seen": True, "confirmation_seen": False},
        MonitorFaultClass.UNCONFIRMED_HIGH_RISK_WRITE,
    ),
    *((f"clean-{index:02d}", {}, None) for index in range(1, 14)),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    monitor = DeterministicMonitor()
    records: list[dict[str, object]] = []
    true_positive = false_positive = false_negative = harmful_interventions = 0
    for case_id, updates, gold in CASES:
        observation = MonitorObservation(
            scenario_id=case_id,
            available_scopes=frozenset(MonitorScope),
        ).model_copy(update=updates)
        report = monitor.evaluate(observation)
        predicted = {item.fault_class for item in report.findings}
        if gold is not None and gold in predicted:
            true_positive += 1
        if gold is not None and gold not in predicted:
            false_negative += 1
        unexpected = predicted - ({gold} if gold is not None else set())
        false_positive += len(unexpected)
        if gold is None and report.findings:
            harmful_interventions += 1
        records.append(
            {
                "case_id": case_id,
                "gold": gold.value if gold else None,
                "predicted": sorted(item.value for item in predicted),
            }
        )
    precision = true_positive / (true_positive + false_positive)
    recall = true_positive / (true_positive + false_negative)
    clean_count = sum(gold is None for _, _, gold in CASES)
    payload = {
        "experiment": "phase7_monitor_calibration",
        "code_revision": args.code_revision,
        "monitor_version": monitor.version,
        "case_count": len(CASES),
        "fault_class_count": len(MonitorFaultClass),
        "metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "harmful_intervention_rate": round(harmful_interventions / clean_count, 4),
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
        },
        "case_manifest_sha256": hashlib.sha256(
            json.dumps(
                [
                    (case_id, updates, gold.value if gold else None)
                    for case_id, updates, gold in CASES
                ],
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest(),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
