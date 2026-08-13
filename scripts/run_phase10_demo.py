#!/usr/bin/env python3
"""Run four CPU-only portfolio demos and build a self-contained trace viewer."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from servicepilot.delivery import render_trace_viewer
from servicepilot.domain.models import OrderStatus
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.judge import DeterministicJudge
from servicepilot.eval.models import ExpectedFinalState, Intent
from servicepilot.eval.runner import run_scenario


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument(
        "--bundle-output", type=Path, default=Path("artifacts/demo/phase10_demo.json")
    )
    parser.add_argument(
        "--trace-output", type=Path, default=Path("artifacts/demo/phase10_demo.jsonl")
    )
    parser.add_argument(
        "--viewer-output", type=Path, default=Path("artifacts/demo/trace_viewer.html")
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    catalog = build_phase3_scenarios()
    specifications = (
        (
            "successful_transaction",
            "成功的高风险交易",
            "退款先 preview、用户确认后 execute，最终状态由 Judge 验证。",
            next(
                item for item in catalog if item.intent is Intent.PARTIAL_REFUND and not item.faults
            ),
        ),
        (
            "fault_recovery",
            "临时故障恢复且无重复写入",
            "preview 首次发生 transient failure，Gateway 有限重试后只产生一笔退款。",
            next(item for item in catalog if item.intent is Intent.PARTIAL_REFUND and item.faults),
        ),
        (
            "confirmation_refusal",
            "用户拒绝高风险确认",
            "用户拒绝取消后 execute 被禁止，订单保持原状态且不构成 false-success。",
            next(
                item
                for item in catalog
                if item.intent is Intent.CANCEL_ORDER and not item.accept_confirmation
            ),
        ),
    )
    demos = []
    traces = []
    for demo_id, title, description, scenario in specifications:
        trajectory, judge, repository = await run_scenario(scenario)
        extra = {}
        if demo_id == "fault_recovery":
            extra["refund_count"] = len(repository.list_refunds(scenario.order_id))
        demos.append(
            {
                "demo_id": demo_id,
                "title": title,
                "description": description,
                "scenario_id": scenario.scenario_id,
                "trajectory": trajectory.model_dump(mode="json"),
                "judge": judge.model_dump(mode="json"),
                "expected_demo_outcome": judge.task_success,
                **extra,
            }
        )
        traces.append(trajectory.model_dump(mode="json"))

    scenario = next(item for item in catalog if item.intent is Intent.ORDER_QUERY)
    trajectory, _, repository = await run_scenario(scenario)
    impossible = scenario.model_copy(
        update={
            "expected": ExpectedFinalState(
                order_status=OrderStatus.CANCELLED,
                write_expected=True,
            )
        }
    )
    judge = DeterministicJudge().evaluate(impossible, trajectory, repository)
    demos.append(
        {
            "demo_id": "false_success_interception",
            "title": "False-success 拦截",
            "description": "Agent 声称成功，但权威订单状态未达到预期；Judge 独立判定失败。",
            "scenario_id": scenario.scenario_id,
            "trajectory": trajectory.model_dump(mode="json"),
            "judge": judge.model_dump(mode="json"),
            "expected_demo_outcome": judge.false_success and not judge.task_success,
        }
    )
    traces.append(trajectory.model_dump(mode="json"))
    if not all(item["expected_demo_outcome"] for item in demos):
        raise RuntimeError("one or more Phase 10 demo acceptance checks failed")
    payload = {
        "schema_version": "servicepilot-phase10-demo-v1",
        "code_revision": args.code_revision,
        "demo_count": len(demos),
        "all_expected_outcomes_observed": True,
        "demos": demos,
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    args.bundle_output.parent.mkdir(parents=True, exist_ok=True)
    args.trace_output.parent.mkdir(parents=True, exist_ok=True)
    args.viewer_output.parent.mkdir(parents=True, exist_ok=True)
    args.bundle_output.write_text(encoded, encoding="utf-8")
    args.trace_output.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in traces),
        encoding="utf-8",
    )
    args.viewer_output.write_text(render_trace_viewer(demos), encoding="utf-8")
    print(
        json.dumps(
            {
                "demo_count": len(demos),
                "all_expected_outcomes_observed": True,
                "bundle_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
                "bundle_output": str(args.bundle_output),
                "trace_output": str(args.trace_output),
                "viewer_output": str(args.viewer_output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
