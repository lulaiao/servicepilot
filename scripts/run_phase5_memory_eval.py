#!/usr/bin/env python3
"""Run the deterministic Phase 5 layered-memory evaluation."""

import argparse
import hashlib
import json
from pathlib import Path

from servicepilot.memory.benchmark import run_memory_benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/phase5_memory_eval.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = run_memory_benchmark()
    serialized_cases = [item.model_dump(mode="json") for item in cases]
    case_bytes = b"\n".join(item.model_dump_json().encode() for item in cases)
    payload = {
        "code_revision": args.code_revision,
        "case_count": len(cases),
        "case_sha256": hashlib.sha256(case_bytes).hexdigest(),
        "no_memory_success_count": sum(item.no_memory_success for item in cases),
        "no_memory_success_rate": round(
            sum(item.no_memory_success for item in cases) / len(cases), 4
        ),
        "layered_memory_success_count": sum(item.layered_memory_success for item in cases),
        "layered_memory_success_rate": round(
            sum(item.layered_memory_success for item in cases) / len(cases), 4
        ),
        "safety_case_count": sum(item.safety_case for item in cases),
        "cases": serialized_cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
