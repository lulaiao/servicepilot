#!/usr/bin/env python3
"""Run one bounded offline LoRA optimizer step and verify adapter reload."""

import argparse
import hashlib
import json
import math
import resource
import time
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

from servicepilot.training import (
    DataSplit,
    SFTExperimentProtocol,
    SFTTrainingRecord,
    assistant_only_labels,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--max-length", type=int)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=20260808)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the Phase 9 LoRA smoke test")
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.cuda.reset_peak_memory_stats()
    protocol = (
        SFTExperimentProtocol.model_validate_json(args.protocol.read_text(encoding="utf-8"))
        if args.protocol
        else None
    )
    if protocol and protocol.model_revision != args.model_revision:
        raise RuntimeError("model revision does not match frozen protocol")
    dataset_sha256 = file_sha256(args.dataset)
    if protocol and protocol.train_sha256 != dataset_sha256:
        raise RuntimeError("dataset hash does not match frozen protocol")
    max_length = args.max_length or (protocol.budget.max_length if protocol else 512)
    lora_r = protocol.lora.rank if protocol else args.lora_r
    lora_alpha = protocol.lora.alpha if protocol else args.lora_alpha
    lora_dropout = protocol.lora.dropout if protocol else args.lora_dropout
    target_modules = (
        protocol.lora.target_modules if protocol else ("q_proj", "k_proj", "v_proj", "o_proj")
    )
    records = tuple(
        SFTTrainingRecord.model_validate_json(line)
        for line in args.dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    train_records = tuple(item for item in records if item.split is DataSplit.TRAIN)
    if not train_records:
        raise RuntimeError("no train records found")
    record = train_records[0]
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    prefixes = []
    messages: list[dict[str, str]] = []
    for message in record.messages:
        messages.append(dict(message))
        prefixes.append(
            tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=False,
            )
        )
    input_ids, labels = assistant_only_labels(
        prefixes, tuple(message["role"] for message in record.messages)
    )
    input_tensor = torch.tensor([input_ids[:max_length]], dtype=torch.long, device="cuda")
    label_tensor = torch.tensor([labels[:max_length]], dtype=torch.long, device="cuda")
    labelled_tokens = int((label_tensor != -100).sum().item())
    if labelled_tokens == 0:
        raise RuntimeError("truncation removed every assistant label")
    load_started = time.perf_counter()
    base = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
    ).to("cuda")
    model = get_peft_model(
        base,
        LoraConfig(
            r=lora_r,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            target_modules=target_modules,
            task_type="CAUSAL_LM",
        ),
    )
    model.train()
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=1e-4,
    )
    load_seconds = time.perf_counter() - load_started
    step_started = time.perf_counter()
    output = model(input_ids=input_tensor, labels=label_tensor)
    loss = float(output.loss.detach().cpu())
    if not math.isfinite(loss):
        raise RuntimeError(f"non-finite smoke loss: {loss}")
    output.loss.backward()
    gradient_norm = float(
        torch.nn.utils.clip_grad_norm_(
            tuple(parameter for parameter in model.parameters() if parameter.requires_grad),
            max_norm=1.0,
        )
        .detach()
        .cpu()
    )
    optimizer.step()
    optimizer.zero_grad(set_to_none=True)
    torch.cuda.synchronize()
    step_seconds = time.perf_counter() - step_started
    args.checkpoint.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.checkpoint, safe_serialization=True)
    optimizer_path = args.checkpoint / "optimizer.pt"
    torch.save(optimizer.state_dict(), optimizer_path)
    adapter_path = args.checkpoint / "adapter_model.safetensors"
    adapter_sha256 = file_sha256(adapter_path)
    del optimizer, output, model, base
    torch.cuda.empty_cache()
    resumed_base = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
    ).to("cuda")
    resumed = PeftModel.from_pretrained(resumed_base, args.checkpoint, is_trainable=True)
    resumed_optimizer = torch.optim.AdamW(
        (parameter for parameter in resumed.parameters() if parameter.requires_grad),
        lr=1e-4,
    )
    resumed_optimizer.load_state_dict(
        torch.load(optimizer_path, map_location="cuda", weights_only=True)
    )
    resumed_trainable = sum(
        parameter.numel() for parameter in resumed.parameters() if parameter.requires_grad
    )
    payload = {
        "experiment": "phase9_lora_smoke",
        "claim_scope": "pipeline_validation_only_not_model_quality",
        "code_revision": args.code_revision,
        "model_path": str(args.model_path),
        "model_revision": args.model_revision,
        "dataset": str(args.dataset),
        "dataset_sha256": dataset_sha256,
        "source_record_id": record.source_record_id,
        "split": record.split.value,
        "seed": args.seed,
        "protocol": str(args.protocol) if args.protocol else None,
        "dtype": "bfloat16",
        "lora": {
            "r": lora_r,
            "alpha": lora_alpha,
            "dropout": lora_dropout,
            "targets": list(target_modules),
        },
        "metrics": {
            "loss": round(loss, 6),
            "gradient_norm_before_clip": round(gradient_norm, 6),
            "input_tokens": input_tensor.numel(),
            "labelled_assistant_tokens": labelled_tokens,
            "model_load_seconds": round(load_seconds, 4),
            "optimizer_step_seconds": round(step_seconds, 4),
            "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
            "peak_vram_reserved_mib": round(torch.cuda.max_memory_reserved() / 1024**2, 2),
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        },
        "checkpoint": {
            "path": str(args.checkpoint),
            "adapter_sha256": adapter_sha256,
            "optimizer_sha256": file_sha256(optimizer_path),
            "reload_succeeded": True,
            "resumed_trainable_parameters": resumed_trainable,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
