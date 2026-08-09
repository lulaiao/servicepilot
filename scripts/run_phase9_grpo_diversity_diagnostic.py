#!/usr/bin/env python3
"""Run a frozen inference-only diversity grid before another GRPO smoke."""

import argparse
import json
import resource
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from servicepilot.eval.catalog import build_phase3_scenarios
    from servicepilot.routing.structured_output import build_intent_prompt
    from servicepilot.training.diversity import DiversitySample, summarize_diversity
    from servicepilot.training.on_policy import ExecutableClassifierReward

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol["claim_scope"] != "inference_only_no_parameter_updates":
        raise RuntimeError("diversity diagnostic must be inference-only")
    if protocol["sealed_records"] != 0:
        raise RuntimeError("diversity diagnostic cannot load sealed records")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for diversity diagnostic")

    catalog = {item.scenario_id: item for item in build_phase3_scenarios()}
    scenarios = tuple(catalog[item] for item in protocol["scenario_ids"])
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
    )
    model = PeftModel.from_pretrained(base, protocol["adapter"], is_trainable=False).cuda()
    model.eval()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    setting_reports = []
    all_evidence = []
    for setting_index, temperature in enumerate(protocol["temperatures"]):
        torch.manual_seed(protocol["seed"] + setting_index)
        torch.cuda.manual_seed_all(protocol["seed"] + setting_index)
        reward_adapter = ExecutableClassifierReward(scenarios)
        samples = []
        for scenario in scenarios:
            rendered = tokenizer.apply_chat_template(
                [{"role": "user", "content": build_intent_prompt(scenario.user_utterance)}],
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = tokenizer(rendered, return_tensors="pt").to("cuda")
            with torch.inference_mode():
                outputs = model.generate(
                    **inputs,
                    do_sample=True,
                    temperature=temperature,
                    num_return_sequences=protocol["num_generations"],
                    max_new_tokens=protocol["max_new_tokens"],
                    pad_token_id=tokenizer.pad_token_id,
                )
            prompt_length = inputs["input_ids"].shape[1]
            completions = tokenizer.batch_decode(
                outputs[:, prompt_length:], skip_special_tokens=True
            )
            for completion in completions:
                evidence = reward_adapter.score(completion, scenario.scenario_id)
                samples.append(
                    DiversitySample(
                        scenario_id=scenario.scenario_id,
                        completion=completion,
                        parsed=evidence.parsed,
                        reward=evidence.reward.total,
                        hard_gate=evidence.reward.hard_gate,
                    )
                )
        summary = summarize_diversity(tuple(samples))
        setting_reports.append(
            {
                "temperature": temperature,
                "summary": summary.model_dump(mode="json"),
            }
        )
        all_evidence.extend(
            {
                "temperature": temperature,
                "evidence": item.model_dump(mode="json"),
            }
            for item in reward_adapter.evidence
        )
    torch.cuda.synchronize()
    payload = {
        "protocol": str(args.protocol),
        "protocol_version": protocol["protocol_version"],
        "claim_scope": protocol["claim_scope"],
        "model_revision": protocol["model_revision"],
        "adapter": protocol["adapter"],
        "sealed_records_loaded": 0,
        "settings": setting_reports,
        "eligible_settings": [
            item["temperature"]
            for item in setting_reports
            if item["summary"]["eligible_for_smoke_retry"]
        ],
        "evidence": all_evidence,
        "resources": {
            "wall_time_seconds": round(time.perf_counter() - started, 4),
            "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
            "peak_vram_reserved_mib": round(torch.cuda.max_memory_reserved() / 1024**2, 2),
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        },
    }
    payload["diagnostic_passed"] = bool(payload["eligible_settings"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
