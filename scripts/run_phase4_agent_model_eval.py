#!/usr/bin/env python3
"""Compare routed rule and learned-extractor Agents in the executable loop."""

import argparse
import asyncio
import json
import math
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.catalog import build_phase3_scenarios
from servicepilot.eval.models import Intent, JudgeResult, Trajectory
from servicepilot.eval.runner import build_report, run_scenario, run_suite
from servicepilot.routing.intent_rules import RuleIntentClassifier
from servicepilot.routing.models import IntentResult, RiskLevel
from servicepilot.routing.structured_output import (
    build_intent_prompt,
    parse_intent_output,
)

INJECTION_PHRASES = (
    "忽略规则",
    "绕过政策",
    "直接修改数据库",
    "调用写工具",
)
HIGH_RISK_INTENTS = {
    Intent.CANCEL_ORDER,
    Intent.FULL_REFUND,
    Intent.PARTIAL_REFUND,
    Intent.MISSING_OR_WRONG_ITEM,
    Intent.DUPLICATE_CHARGE,
    Intent.RESCHEDULE,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--evaluation-split", choices=("dev", "sealed_test"))
    parser.add_argument("--device", choices=("cuda",), default="cuda")
    parser.add_argument(
        "--dtype", choices=("float16", "bfloat16"), default="float16"
    )
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trace-output", type=Path, required=True)
    return parser.parse_args()


class LocalTransformersIntentClassifier:
    """Local model adapter with a deterministic injection guardrail."""

    def __init__(self, args: argparse.Namespace) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required for the formal Agent run")
        self.torch = torch
        self.device = args.device
        self.max_new_tokens = args.max_new_tokens
        self.guardrail = RuleIntentClassifier()
        self.records: list[dict[str, Any]] = []
        dtype = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }[args.dtype]
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
        torch.cuda.reset_peak_memory_stats()
        load_started = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(
            args.model_path, local_files_only=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            args.model_path,
            local_files_only=True,
            torch_dtype=dtype,
        ).to(self.device)
        if args.adapter_path:
            from peft import PeftModel

            self.model = PeftModel.from_pretrained(
                self.model, args.adapter_path, is_trainable=False
            )
        self.model.eval()
        torch.cuda.synchronize()
        self.model_load_seconds = time.perf_counter() - load_started

    def classify(self, text: str) -> IntentResult:
        if any(phrase in text for phrase in INJECTION_PHRASES):
            result = self.guardrail.classify(text)
            self.records.append(
                {
                    "text": text,
                    "source": "deterministic_injection_guardrail",
                    "schema_valid": True,
                    "latency_seconds": 0.0,
                    "prediction": result.model_dump(mode="json"),
                }
            )
            return result
        messages = [
            {"role": "user", "content": build_intent_prompt(text)}
        ]
        rendered = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(rendered, return_tensors="pt").to(self.device)
        self.torch.cuda.synchronize()
        started = time.perf_counter()
        with self.torch.inference_mode():
            output = self.model.generate(
                **inputs,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                max_new_tokens=self.max_new_tokens,
            )
        self.torch.cuda.synchronize()
        latency = time.perf_counter() - started
        generated = self.tokenizer.decode(
            output[0, inputs["input_ids"].shape[1] :],
            skip_special_tokens=True,
        )
        try:
            result = parse_intent_output(generated)
            error = None
        except (ValueError, json.JSONDecodeError) as exc:
            error = f"{type(exc).__name__}: {exc}"
            result = IntentResult(
                primary_intent=Intent.OUT_OF_SCOPE,
                slots={
                    "order_id": None,
                    "reason": None,
                    "requested_amount": None,
                },
                risk_level=RiskLevel.HIGH,
                confidence=0.0,
                needs_clarification=False,
                injection_detected=False,
            )
        self.records.append(
            {
                "text": text,
                "source": "local_model",
                "schema_valid": error is None,
                "latency_seconds": round(latency, 4),
                "prediction": result.model_dump(mode="json"),
                "error": error,
                "raw_output": generated,
            }
        )
        return result


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def risk_metrics(
    scenarios: tuple[Any, ...], results: tuple[JudgeResult, ...]
) -> dict[str, float | int]:
    by_id = {item.scenario_id: item for item in results}
    selected = [item for item in scenarios if item.intent in HIGH_RISK_INTENTS]
    failures = sum(not by_id[item.scenario_id].task_success for item in selected)
    unsafe = sum(
        (
            not by_id[item.scenario_id].policy_compliant
            or not by_id[item.scenario_id].tool_sequence_valid
            or by_id[item.scenario_id].false_success
        )
        for item in selected
    )
    return {
        "high_risk_scenario_count": len(selected),
        "high_risk_task_failure_rate": round(failures / len(selected), 4),
        "unsafe_high_risk_error_rate": round(unsafe / len(selected), 4),
    }


async def main_async() -> None:
    args = parse_args()
    import torch

    scenarios = build_phase3_scenarios()
    rule_started = time.perf_counter()
    rule_trajectories, rule_results, rule_report = await run_suite(
        scenarios, agent_factory=RoutedRuleAgent
    )
    rule_elapsed = time.perf_counter() - rule_started

    print("loading learned extractor", file=sys.stderr, flush=True)
    classifier = LocalTransformersIntentClassifier(args)
    print(
        f"model loaded in {classifier.model_load_seconds:.3f}s",
        file=sys.stderr,
        flush=True,
    )
    model_trajectories: list[Trajectory] = []
    model_results: list[JudgeResult] = []
    scenario_latencies: list[float] = []
    for index, scenario in enumerate(scenarios, start=1):
        print(
            f"scenario {index}/{len(scenarios)}: {scenario.scenario_id}",
            file=sys.stderr,
            flush=True,
        )
        torch.cuda.synchronize()
        started = time.perf_counter()
        try:
            trajectory, result, _ = await run_scenario(
                scenario, agent=RoutedRuleAgent(classifier=classifier)
            )
        except Exception as exc:
            # A learned policy can select an action whose required scenario slot
            # is absent. That is evaluation evidence, not an infrastructure
            # failure: preserve it as an unsafe failed trajectory and continue.
            trajectory = Trajectory(
                scenario_id=scenario.scenario_id,
                trace_id=f"runtime-error-{scenario.scenario_id}",
                events=(),
                claimed_success=False,
                final_message=f"{type(exc).__name__}: {exc}",
                detected_intents=(),
            )
            result = JudgeResult(
                scenario_id=scenario.scenario_id,
                task_success=False,
                final_state_correct=False,
                policy_compliant=False,
                false_success=False,
                tool_sequence_valid=False,
                failure_reasons=("AGENT_RUNTIME_ERROR",),
                turns=0,
                tool_calls=0,
            )
        torch.cuda.synchronize()
        scenario_latencies.append(time.perf_counter() - started)
        model_trajectories.append(trajectory)
        model_results.append(result)
    model_report = build_report(scenarios, model_results)
    inference_latencies = [
        float(item["latency_seconds"])
        for item in classifier.records
        if item["source"] == "local_model"
    ]
    payload = {
        "split": args.evaluation_split,
        "checkpoint": str(args.adapter_path) if args.adapter_path else None,
        "comparison_contract": {
            "scenarios": len(scenarios),
            "tool_budget_per_scenario": 12,
            "gateway_retry_budget": 2,
            "router": "StatefulRouter",
            "action_policy": "shared deterministic RuleBasedSingleAgent",
            "judge": "DeterministicJudge",
            "difference": "intent/slot classifier only",
        },
        "rule_agent": {
            "report": rule_report.model_dump(mode="json"),
            "risk": risk_metrics(scenarios, rule_results),
            "suite_latency_seconds": round(rule_elapsed, 4),
            "mean_scenario_latency_seconds": round(
                rule_elapsed / len(scenarios), 4
            ),
            "peak_vram_allocated_mib": 0.0,
        },
        "learned_extractor_agent": {
            "candidate": {
                "path": str(args.model_path.resolve()),
                "revision": args.revision,
                "adapter_path": str(args.adapter_path.resolve())
                if args.adapter_path
                else None,
                "dtype": args.dtype,
                "device": args.device,
            },
            "runtime": {
                "torch_version": torch.__version__,
                "cuda_runtime": torch.version.cuda,
                "cuda_visible_devices": os.environ.get(
                    "CUDA_VISIBLE_DEVICES"
                ),
                "gpu_name": torch.cuda.get_device_name(0),
                "model_load_seconds": round(
                    classifier.model_load_seconds, 4
                ),
                "peak_rss_mib": round(
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                    1,
                ),
                "peak_vram_allocated_mib": round(
                    torch.cuda.max_memory_allocated() / 1024**2, 1
                ),
                "peak_vram_reserved_mib": round(
                    torch.cuda.max_memory_reserved() / 1024**2, 1
                ),
            },
            "report": model_report.model_dump(mode="json"),
            "risk": risk_metrics(scenarios, tuple(model_results)),
            "mean_scenario_latency_seconds": round(
                sum(scenario_latencies) / len(scenario_latencies), 4
            ),
            "p95_scenario_latency_seconds": round(
                percentile(scenario_latencies, 0.95), 4
            ),
            "mean_inference_latency_seconds": round(
                sum(inference_latencies) / len(inference_latencies), 4
            ),
            "p95_inference_latency_seconds": round(
                percentile(inference_latencies, 0.95), 4
            ),
            "schema_valid_rate": round(
                sum(item["schema_valid"] for item in classifier.records)
                / len(classifier.records),
                4,
            ),
            "classifier_records": classifier.records,
            "runtime_error_count": sum(
                "AGENT_RUNTIME_ERROR" in item.failure_reasons
                for item in model_results
            ),
        },
    }
    learned = payload["learned_extractor_agent"]
    payload["checkpoint_selection_metrics"] = {
        "executable_task_success": learned["report"]["executable_task_success_rate"],
        "high_risk_error_rate": learned["risk"]["unsafe_high_risk_error_rate"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.trace_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    trace_payload = {
        "rule": [item.model_dump(mode="json") for item in rule_trajectories],
        "learned": [item.model_dump(mode="json") for item in model_trajectories],
    }
    args.trace_output.write_text(
        json.dumps(trace_payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "rule_agent": payload["rule_agent"],
                "learned_extractor_agent": {
                    key: value
                    for key, value in payload["learned_extractor_agent"].items()
                    if key != "classifier_records"
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
