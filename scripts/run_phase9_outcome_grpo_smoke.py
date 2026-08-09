#!/usr/bin/env python3
"""Run a one-step executable outcome-reward GRPO pipeline smoke test."""

import argparse
import json
import math
import resource
import time
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    import torch
    from datasets import Dataset
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    from servicepilot.eval.catalog import build_phase3_scenarios
    from servicepilot.training.on_policy import (
        ExecutableClassifierReward,
        classifier_grpo_examples,
        model_owned_scenarios,
    )

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol["claim_scope"] != "pipeline_validation_only":
        raise RuntimeError("smoke protocol cannot make a quality claim")
    if protocol["sealed_records"] != 0:
        raise RuntimeError("GRPO smoke must not load sealed records")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for GRPO smoke")
    torch.manual_seed(protocol["seed"])
    torch.cuda.manual_seed_all(protocol["seed"])
    torch.cuda.reset_peak_memory_stats()

    scenarios = model_owned_scenarios(build_phase3_scenarios())
    selected_scenarios = (scenarios[0], scenarios[len(scenarios) // 2])
    examples = classifier_grpo_examples(selected_scenarios)
    dataset = Dataset.from_list(list(examples))
    reward_adapter = ExecutableClassifierReward(selected_scenarios)

    def executable_outcome_reward(
        prompts: list[Any],
        completions: list[Any],
        scenario_id: list[str],
        **kwargs: Any,
    ) -> list[float]:
        return reward_adapter(
            prompts=prompts,
            completions=completions,
            scenario_id=scenario_id,
            **kwargs,
        )

    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
    )
    model = PeftModel.from_pretrained(
        base,
        protocol["sft_adapter"],
        is_trainable=True,
    )
    training_args = GRPOConfig(
        output_dir=str(args.output_dir),
        max_steps=protocol["max_steps"],
        per_device_train_batch_size=protocol["per_device_train_batch_size"],
        gradient_accumulation_steps=protocol["gradient_accumulation_steps"],
        num_generations=protocol["num_generations"],
        max_prompt_length=protocol["max_prompt_length"],
        max_completion_length=protocol["max_completion_length"],
        temperature=protocol["temperature"],
        learning_rate=protocol["learning_rate"],
        beta=protocol["beta"],
        bf16=True,
        logging_steps=1,
        logging_first_step=True,
        save_strategy="no",
        report_to=[],
        seed=protocol["seed"],
        data_seed=protocol["seed"],
    )
    trainer = GRPOTrainer(
        model=model,
        reward_funcs=executable_outcome_reward,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
    )
    started = time.perf_counter()
    result = trainer.train()
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - started
    log_history = trainer.state.log_history
    reward_stds = [
        float(row["reward_std"])
        for row in log_history
        if row.get("reward_std") is not None
    ]
    train_loss = float(result.training_loss)
    gates = {
        "finite_training_loss": math.isfinite(train_loss),
        "four_executable_reward_evaluations": len(reward_adapter.evidence) == 4,
        "nonzero_group_reward_std": bool(reward_stds) and max(reward_stds) > 0,
        "no_cuda_oom": True,
    }
    payload = {
        "protocol": str(args.protocol),
        "protocol_version": protocol["protocol_version"],
        "claim_scope": protocol["claim_scope"],
        "model_revision": protocol["base_model_revision"],
        "sft_adapter": protocol["sft_adapter"],
        "sealed_records_loaded": 0,
        "train_scenario_ids": [item.scenario_id for item in selected_scenarios],
        "training_loss": train_loss,
        "log_history": log_history,
        "reward_evidence": [item.model_dump(mode="json") for item in reward_adapter.evidence],
        "resources": {
            "wall_time_seconds": round(elapsed, 4),
            "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
            "peak_vram_reserved_mib": round(torch.cuda.max_memory_reserved() / 1024**2, 2),
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        },
        "gates": gates,
        "smoke_passed": all(gates.values()),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
