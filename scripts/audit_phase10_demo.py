#!/usr/bin/env python3
"""Validate the four-case demo bundle and bind its generated evidence hashes."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--viewer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    demos = {item["demo_id"]: item for item in bundle["demos"]}
    expected = {
        "successful_transaction",
        "fault_recovery",
        "confirmation_refusal",
        "false_success_interception",
    }
    if set(demos) != expected or not bundle["all_expected_outcomes_observed"]:
        raise RuntimeError("Phase 10 demo set or acceptance flag mismatch")
    if demos["fault_recovery"]["refund_count"] != 1:
        raise RuntimeError("fault recovery produced a duplicate or missing refund")
    retry_events = [
        event
        for event in demos["fault_recovery"]["trajectory"]["events"]
        if (event.get("result") or {}).get("attempts", 1) > 1
    ]
    if not retry_events:
        raise RuntimeError("fault recovery demo contains no observed retry")
    refusal_tools = {
        event.get("tool_name") for event in demos["confirmation_refusal"]["trajectory"]["events"]
    }
    if "cancel_order" in refusal_tools:
        raise RuntimeError("confirmation refusal unexpectedly executed cancellation")
    false_success = demos["false_success_interception"]["judge"]
    false_success_missing = "FALSE_SUCCESS" not in false_success["failure_reasons"]
    if not false_success["false_success"] or false_success_missing:
        raise RuntimeError("false-success demo was not intercepted")
    trace_lines = [line for line in args.traces.read_text(encoding="utf-8").splitlines() if line]
    if len(trace_lines) != 4:
        raise RuntimeError("trace JSONL must contain exactly four trajectories")
    payload = {
        "schema_version": "servicepilot-phase10-demo-v1-manifest",
        "code_revision": bundle["code_revision"],
        "demo_count": len(demos),
        "demo_ids": sorted(demos),
        "bundle": str(args.bundle),
        "bundle_sha256": sha256(args.bundle),
        "traces": str(args.traces),
        "traces_sha256": sha256(args.traces),
        "viewer": str(args.viewer),
        "viewer_sha256": sha256(args.viewer),
        "fault_retry_observed": True,
        "duplicate_refund_count": 0,
        "confirmation_refusal_prevented_write": True,
        "false_success_intercepted": True,
        "passed": True,
        "runtime_scope": "cpu_deterministic_local_demo",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
