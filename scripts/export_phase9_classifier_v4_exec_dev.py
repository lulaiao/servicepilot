#!/usr/bin/env python3
"""Freeze executable scenarios for classifier v4 development selection."""

import argparse
import hashlib
import json
from pathlib import Path

from servicepilot.training import build_classifier_v4_dev_scenarios


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    scenarios = build_classifier_v4_dev_scenarios()
    encoded = "".join(item.model_dump_json() + "\n" for item in scenarios).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    payload = {
        "schema_version": "servicepilot-classifier-v4-executable-dev",
        "code_revision": args.code_revision,
        "scenario_count": len(scenarios),
        "output": str(args.output),
        "output_sha256": hashlib.sha256(encoded).hexdigest(),
        "train_scenario_count": 0,
        "sealed_scenario_count": 0,
        "hard_eval_v2_accessed": False,
        "passed": len(scenarios) == 36,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
