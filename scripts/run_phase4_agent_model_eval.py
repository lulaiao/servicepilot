#!/usr/bin/env python3
"""Compare routed rule and learned-extractor Agents in the executable loop."""

import argparse
import asyncio
import hashlib
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
from servicepilot.eval.hard_catalog import HardEvalCase
from servicepilot.eval.models import Intent, JudgeResult, ScenarioSpec, Trajectory
from servicepilot.eval.runner import build_report, run_scenario, run_suite
from servicepilot.routing.intent_rules import RuleIntentClassifier
from servicepilot.routing.models import IntentResult, RiskLevel
from servicepilot.routing.structured_output import (
    build_intent_prompt,
    parse_intent_output,
)
from servicepilot.training.classifier_data import classifier_target

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
    parser.add_argument("--evaluation-split", choices=("dev", "sealed_test", "hard_eval_v2"))
    parser.add_argument("--scenario-catalog", type=Path)
    parser.add_argument("--device", choices=("cuda",), default="cuda")
    parser.add_argument("--dtype", choices=("float16", "bfloat16"), default="float16")
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
        self.tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
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
        messages = [{"role": "user", "content": build_intent_prompt(text)}]
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


def load_scenarios(path: Path | None) -> tuple[ScenarioSpec, ...]:
    if path is None:
        return build_phase3_scenarios()
    cases = tuple(
        HardEvalCase.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if not cases:
        raise ValueError("scenario catalog is empty")
    return tuple(item.scenario for item in cases)


def raw_classifier_metrics(
    scenarios: tuple[ScenarioSpec, ...], records: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(records) != len(scenarios):
        raise ValueError("classifier record count does not match scenario count")
    labels = tuple(Intent)
    targets = [classifier_target(item) for item in scenarios]
    gold = [item.primary_intent for item in targets]
    predicted = [Intent(item["prediction"]["primary_intent"]) for item in records]
    per_intent: dict[str, dict[str, float | int]] = {}
    f1_values = []
    for label in labels:
        pairs = tuple(zip(gold, predicted, strict=True))
        true_positive = sum(g is label and p is label for g, p in pairs)
        false_positive = sum(g is not label and p is label for g, p in pairs)
        false_negative = sum(g is label and p is not label for g, p in pairs)
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_intent[label.value] = {
            "support": sum(item is label for item in gold),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return {
        "primary_accuracy": round(
            sum(g is p for g, p in zip(gold, predicted, strict=True)) / len(gold), 4
        ),
        "primary_macro_f1": round(sum(f1_values) / len(f1_values), 4),
        "schema_valid_rate": round(sum(item["schema_valid"] for item in records) / len(records), 4),
        "executable_intent_tuple_accuracy": round(
            sum(
                (
                    Intent(record["prediction"]["primary_intent"]),
                    *tuple(Intent(item) for item in record["prediction"]["secondary_intents"]),
                )
                == (target.primary_intent, *target.secondary_intents)
                for target, record in zip(targets, records, strict=True)
            )
            / len(records),
            4,
        ),
        "per_intent": per_intent,
    }


def guardrail_effect_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    interventions = [item for item in records if item["intervention_type"] is not None]
    return {
        "intervention_count": len(interventions),
        "rescue_count": sum(item["effect"] == "rescue" for item in interventions),
        "harm_count": sum(item["effect"] == "harm" for item in interventions),
        "neutral_count": sum(item["effect"] == "neutral" for item in interventions),
        "records": interventions,
    }


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

    scenarios = load_scenarios(args.scenario_catalog)
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
    safety_override_count = 0
    tool_alignment_override_count = 0
    guardrail_records: list[dict[str, Any]] = []
    for index, scenario in enumerate(scenarios, start=1):
        print(
            f"scenario {index}/{len(scenarios)}: {scenario.scenario_id}",
            file=sys.stderr,
            flush=True,
        )
        torch.cuda.synchronize()
        started = time.perf_counter()
        agent = RoutedRuleAgent(classifier=classifier)
        try:
            trajectory, result, _ = await run_scenario(scenario, agent=agent)
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
        safety_override_count += agent.safety_override_count
        tool_alignment_override_count += agent.tool_alignment_override_count
        raw_record = classifier.records[-1]
        raw_intents = (
            Intent(raw_record["prediction"]["primary_intent"]),
            *tuple(Intent(item) for item in raw_record["prediction"]["secondary_intents"]),
        )
        expected = classifier_target(scenario)
        expected_intents = (expected.primary_intent, *expected.secondary_intents)
        selected_intents = (
            (agent.state.intent.primary_intent, *agent.state.intent.secondary_intents)
            if agent.state is not None
            else ()
        )
        intervention_type = None
        if agent.safety_override_count:
            intervention_type = "deterministic_safety"
        elif agent.tool_alignment_override_count:
            intervention_type = "tool_alignment"
        raw_correct = raw_intents == expected_intents
        selected_correct = selected_intents == expected_intents
        effect = "neutral"
        if not raw_correct and selected_correct:
            effect = "rescue"
        elif raw_correct and not selected_correct:
            effect = "harm"
        guardrail_records.append(
            {
                "scenario_id": scenario.scenario_id,
                "intervention_type": intervention_type,
                "raw_intents": [item.value for item in raw_intents],
                "selected_intents": [item.value for item in selected_intents],
                "expected_intents": [item.value for item in expected_intents],
                "effect": effect,
            }
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
            "scenario_catalog": str(args.scenario_catalog) if args.scenario_catalog else None,
            "scenario_catalog_sha256": hashlib.sha256(
                args.scenario_catalog.read_bytes()
            ).hexdigest()
            if args.scenario_catalog
            else None,
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
            "mean_scenario_latency_seconds": round(rule_elapsed / len(scenarios), 4),
            "peak_vram_allocated_mib": 0.0,
        },
        "learned_extractor_agent": {
            "candidate": {
                "path": str(args.model_path.resolve()),
                "revision": args.revision,
                "adapter_path": str(args.adapter_path.resolve()) if args.adapter_path else None,
                "dtype": args.dtype,
                "device": args.device,
            },
            "runtime": {
                "torch_version": torch.__version__,
                "cuda_runtime": torch.version.cuda,
                "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "gpu_name": torch.cuda.get_device_name(0),
                "model_load_seconds": round(classifier.model_load_seconds, 4),
                "peak_rss_mib": round(
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                    1,
                ),
                "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
                "peak_vram_reserved_mib": round(torch.cuda.max_memory_reserved() / 1024**2, 1),
            },
            "report": model_report.model_dump(mode="json"),
            "risk": risk_metrics(scenarios, tuple(model_results)),
            "mean_scenario_latency_seconds": round(
                sum(scenario_latencies) / len(scenario_latencies), 4
            ),
            "p95_scenario_latency_seconds": round(percentile(scenario_latencies, 0.95), 4),
            "mean_inference_latency_seconds": round(
                sum(inference_latencies) / len(inference_latencies), 4
            ),
            "p95_inference_latency_seconds": round(percentile(inference_latencies, 0.95), 4),
            "schema_valid_rate": round(
                sum(item["schema_valid"] for item in classifier.records) / len(classifier.records),
                4,
            ),
            "raw_classifier": raw_classifier_metrics(scenarios, classifier.records),
            "classifier_records": classifier.records,
            "runtime_error_count": sum(
                "AGENT_RUNTIME_ERROR" in item.failure_reasons for item in model_results
            ),
            "deterministic_safety_override_count": safety_override_count,
            "tool_alignment_override_count": tool_alignment_override_count,
            "guardrail_effects": guardrail_effect_metrics(guardrail_records),
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
