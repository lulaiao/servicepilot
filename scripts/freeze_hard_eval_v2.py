#!/usr/bin/env python3
"""Freeze Hard Eval v2 and validate rule executability and lexical independence."""

import argparse
import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path

from servicepilot.agents.routed_baseline import RoutedRuleAgent
from servicepilot.eval.hard_catalog import ScenarioGoldAgent, build_hard_eval_v2
from servicepilot.harness.evaluation import EvaluationHarness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-data", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def normalize(text: str) -> str:
    return "".join(text.lower().split())


def shingles(text: str, size: int = 5) -> set[str]:
    value = normalize(text)
    return {value[index : index + size] for index in range(max(1, len(value) - size + 1))}


async def main() -> None:
    args = parse_args()
    cases = build_hard_eval_v2()
    encoded = "".join(item.model_dump_json() + "\n" for item in cases).encode()
    training_prompts = []
    for line in args.training_data.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["split"] == "train":
            prompt = record["messages"][0]["content"]
            training_prompts.append(prompt.rsplit("用户输入：", maxsplit=1)[-1])
    train_normalized = {normalize(item) for item in training_prompts}
    exact_overlap = sum(
        normalize(case.scenario.user_utterance) in train_normalized for case in cases
    )
    train_shingles = [(text, shingles(text)) for text in training_prompts]
    near_pairs = []
    for case in cases:
        left = shingles(case.scenario.user_utterance)
        best = 0.0
        for _, right in train_shingles:
            union = left | right
            score = len(left & right) / len(union) if union else 1.0
            best = max(best, score)
        if best >= 0.9:
            near_pairs.append((case.case_id, round(best, 4)))

    harness = EvaluationHarness(code_revision=args.code_revision)
    failures = []
    for case in cases:
        agent = ScenarioGoldAgent(case.scenario)
        _, judge, _ = await harness.run_scenario(case.scenario, agent=agent)
        if not judge.task_success:
            failures.append({"case_id": case.case_id, "failure_reasons": judge.failure_reasons})
    scenarios = tuple(item.scenario for item in cases)
    _, rule_results, rule_report = await harness.run_suite(scenarios, agent_factory=RoutedRuleAgent)
    rule_failure_count = sum(not item.task_success for item in rule_results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    counts = Counter(item.scenario.intent.value for item in cases)
    payload = {
        "catalog_version": "servicepilot-hard-eval-v2",
        "provenance": "post_training_independent_compositional_authoring",
        "code_revision": args.code_revision,
        "case_count": len(cases),
        "intent_counts": dict(sorted(counts.items())),
        "compositional_dimensions": {"issue": 4, "request": 5},
        "training_data": str(args.training_data),
        "training_data_sha256": hashlib.sha256(args.training_data.read_bytes()).hexdigest(),
        "exact_training_utterance_overlap_count": exact_overlap,
        "near_duplicate_threshold": 0.9,
        "near_duplicate_count": len(near_pairs),
        "near_duplicates": near_pairs,
        "gold_routed_workflow_success_count": len(cases) - len(failures),
        "gold_routed_workflow_failures": failures,
        "rule_baseline": rule_report.model_dump(mode="json"),
        "rule_baseline_failure_count": rule_failure_count,
        "catalog": str(args.output),
        "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "freeze_passed": exact_overlap == 0 and not near_pairs and not failures,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
