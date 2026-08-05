#!/usr/bin/env python3
"""Run the deterministic Phase 3 suite and persist reproducible JSON artifacts."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.runner import run_suite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=Path("artifacts/traces/phase3_trajectories.jsonl"),
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("artifacts/reports/phase3_report.json"),
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=Path("artifacts/reports/phase3_manifest.json"),
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    scenarios = build_phase3_scenarios()
    trajectories, _, report = await run_suite(scenarios)
    scenario_payload = "\n".join(
        scenario.model_dump_json() for scenario in scenarios
    ).encode()
    args.trace_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.trace_output.write_text(
        "\n".join(item.model_dump_json() for item in trajectories) + "\n",
        encoding="utf-8",
    )
    args.report_output.write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "scenario_count": len(scenarios),
        "scenario_sha256": hashlib.sha256(scenario_payload).hexdigest(),
        "trace_output": str(args.trace_output),
        "report_output": str(args.report_output),
        "generator": "servicepilot.eval.catalog.build_phase3_scenarios",
        "seed": 20260805,
        "judge": "deterministic",
    }
    args.manifest_output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(report.model_dump_json(indent=2))


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
