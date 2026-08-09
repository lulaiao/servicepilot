#!/usr/bin/env python3
"""Run a bounded dev-only outcome GRPO screen with fail-closed termination."""

import argparse
import json
import math
import resource
import time
from pathlib import Path
from typing import Any


class SafetyTermination(RuntimeError):
    """Stop before an optimizer update when a sampled group violates a hard gate."""


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
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainerCallback
    from trl import GRPOConfig, GRPOTrainer

    from servicepilot.eval.catalog import build_phase3_scenarios
    from servicepilot.training.on_policy import (
        ExecutableClassifierReward,
        classifier_grpo_examples,
        model_owned_scenarios,
    )

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol["claim_scope"] != "single_seed_dev_screening_no_quality_claim":
        raise RuntimeError("bounded runner requires the screening claim scope")
    if protocol["sealed_records"] != 0:
        raise RuntimeError("bounded GRPO screen cannot load sealed records")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for bounded GRPO screening")
    torch.manual_seed(protocol["seed"])
    torch.cuda.manual_seed_all(protocol["seed"])
    torch.cuda.reset_peak_memory_stats()

    catalog = {
        item.scenario_id: item
        for item in model_owned_scenarios(build_phase3_scenarios())
    }
    scenarios = tuple(catalog[item] for item in protocol["scenario_ids"])
    dataset = Dataset.from_list(list(classifier_grpo_examples(scenarios)))
    reward_adapter = ExecutableClassifierReward(scenarios)
    termination_reason: str | None = None

    def executable_outcome_reward(
        prompts: list[Any],
        completions: list[Any],
        scenario_id: list[str],
        **kwargs: Any,
    ) -> list[float]:
        start = len(reward_adapter.evidence)
        rewards = reward_adapter(
            prompts=prompts,
            completions=completions,
            scenario_id=scenario_id,
            **kwargs,
        )
        recent = reward_adapter.evidence[start:]
        schema_rate = sum(item.parsed for item in recent) / len(recent)
        if schema_rate < protocol["termination"]["minimum_batch_schema_valid_rate"]:
            raise SafetyTermination("batch_schema_valid_rate_below_threshold")
        forbidden = {"unsafe", "false_success"}
        hard_gates = {item.reward.hard_gate for item in recent}
        if forbidden.intersection(hard_gates):
            raise SafetyTermination("unsafe_or_false_success_reward_hard_gate")
        return rewards

    class KlTerminationCallback(TrainerCallback):
        exceeded = False

        def on_log(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
            del args, state
            logs = kwargs.get("logs", {})
            if logs.get("kl", 0.0) > protocol["termination"]["maximum_kl"]:
                self.exceeded = True
                control.should_training_stop = True
            return control

    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.model_path, local_files_only=True, torch_dtype=torch.bfloat16
    )
    model = PeftModel.from_pretrained(base, protocol["sft_adapter"], is_trainable=True)
    trainable_before = {
        name: parameter.detach().float().cpu().clone()
        for name, parameter in model.named_parameters()
        if parameter.requires_grad
    }
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
        lr_scheduler_type=protocol["lr_scheduler_type"],
        beta=protocol["beta"],
        bf16=True,
        logging_steps=1,
        logging_first_step=True,
        save_strategy="no",
        report_to=[],
        seed=protocol["seed"],
        data_seed=protocol["seed"],
    )
    kl_callback = KlTerminationCallback()
    trainer = GRPOTrainer(
        model=model,
        reward_funcs=executable_outcome_reward,
        args=training_args,
        train_dataset=dataset,
        processing_class=tokenizer,
        callbacks=[kl_callback],
    )
    started = time.perf_counter()
    training_loss = math.nan
    try:
        result = trainer.train()
        training_loss = float(result.training_loss)
    except SafetyTermination as exc:
        termination_reason = str(exc)
    if kl_callback.exceeded:
        termination_reason = "kl_above_threshold"
    torch.cuda.synchronize()

    parameter_delta_squared = 0.0
    for name, parameter in model.named_parameters():
        if name in trainable_before:
            difference = parameter.detach().float().cpu() - trainable_before[name]
            parameter_delta_squared += float((difference * difference).sum())
    parameter_delta_l2 = math.sqrt(parameter_delta_squared)
    log_history = trainer.state.log_history
    reward_stds = [float(row["reward_std"]) for row in log_history if "reward_std" in row]
    kl_values = [float(row["kl"]) for row in log_history if "kl" in row]
    schema_valid_rate = (
        sum(item.parsed for item in reward_adapter.evidence) / len(reward_adapter.evidence)
        if reward_adapter.evidence
        else 0.0
    )
    runtime_error_rate = (
        sum(item.runtime_error is not None for item in reward_adapter.evidence)
        / len(reward_adapter.evidence)
        if reward_adapter.evidence
        else 0.0
    )
    completed = termination_reason is None and trainer.state.global_step == protocol["max_steps"]
    gates = {
        "completed_all_steps": completed,
        "finite_training_loss": math.isfinite(training_loss),
        "schema_valid_rate": schema_valid_rate
        >= protocol["completion_gates"]["minimum_schema_valid_rate"],
        "nonzero_reward_std_steps": sum(value > 0 for value in reward_stds)
        >= protocol["completion_gates"]["minimum_nonzero_reward_std_steps"],
        "runtime_error_rate": runtime_error_rate
        <= protocol["completion_gates"]["maximum_runtime_error_rate"],
        "kl_within_limit": not kl_values
        or max(kl_values) <= protocol["termination"]["maximum_kl"],
        "parameter_updated": parameter_delta_l2 > 0,
        "no_safety_termination": termination_reason is None,
    }
    final_adapter = args.output_dir / "final-adapter"
    if all(gates.values()):
        model.save_pretrained(final_adapter)
        tokenizer.save_pretrained(final_adapter)
    payload = {
        "protocol": str(args.protocol),
        "protocol_version": protocol["protocol_version"],
        "claim_scope": protocol["claim_scope"],
        "model_revision": protocol["base_model_revision"],
        "sft_adapter": protocol["sft_adapter"],
        "sealed_records_loaded": 0,
        "train_scenario_ids": [item.scenario_id for item in scenarios],
        "completed_steps": trainer.state.global_step,
        "termination_reason": termination_reason,
        "training_loss": training_loss if math.isfinite(training_loss) else None,
        "parameter_delta_l2": parameter_delta_l2,
        "schema_valid_rate": schema_valid_rate,
        "runtime_error_rate": runtime_error_rate,
        "maximum_kl": max(kl_values) if kl_values else None,
        "nonzero_reward_std_steps": sum(value > 0 for value in reward_stds),
        "log_history": log_history,
        "reward_evidence": [item.model_dump(mode="json") for item in reward_adapter.evidence],
        "final_adapter": str(final_adapter) if all(gates.values()) else None,
        "resources": {
            "wall_time_seconds": round(time.perf_counter() - started, 4),
            "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
            "peak_vram_reserved_mib": round(torch.cuda.max_memory_reserved() / 1024**2, 2),
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        },
        "gates": gates,
        "screen_passed": all(gates.values()),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
