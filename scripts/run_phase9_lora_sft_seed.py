#!/usr/bin/env python3
"""Train one frozen Phase 9 LoRA seed and emit resumable checkpoint evidence."""

import argparse
import hashlib
import json
import math
import resource
import time
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, get_peft_model
from torch.utils.data import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)

from servicepilot.training import (
    CheckpointEvidence,
    DataSplit,
    SeedRunState,
    SFTExperimentProtocol,
    SFTTrainingRecord,
    assistant_only_labels,
    checkpoint_step,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--max-steps", type=int, default=-1)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TokenizedSFTDataset(Dataset[dict[str, list[int]]]):
    def __init__(self, records: tuple[SFTTrainingRecord, ...], tokenizer: Any, limit: int):
        self.examples: list[dict[str, list[int]]] = []
        for record in records:
            prefixes: list[list[int]] = []
            messages: list[dict[str, str]] = []
            for message in record.messages:
                messages.append(dict(message))
                prefixes.append(
                    tokenizer.apply_chat_template(
                        messages, tokenize=True, add_generation_prompt=False
                    )
                )
            input_ids, labels = assistant_only_labels(
                prefixes, tuple(message["role"] for message in record.messages)
            )
            input_ids = input_ids[:limit]
            labels = labels[:limit]
            if not any(label != -100 for label in labels):
                raise RuntimeError(f"truncation removed labels for {record.source_record_id}")
            self.examples.append(
                {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels}
            )

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> dict[str, list[int]]:
        return self.examples[index]


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    protocol = SFTExperimentProtocol.model_validate_json(
        args.protocol.read_text(encoding="utf-8")
    )
    if args.seed not in protocol.seeds:
        raise RuntimeError("seed is not declared in the frozen protocol")
    if args.max_steps > 0 and (
        args.seed != protocol.screening_seed
        or args.max_steps != protocol.screening_max_steps
    ):
        raise RuntimeError("bounded screening run does not match the frozen protocol")
    data_path = Path(protocol.train_data)
    if file_sha256(data_path) != protocol.train_sha256:
        raise RuntimeError("dataset hash does not match the frozen protocol")
    records = tuple(
        SFTTrainingRecord.model_validate_json(line)
        for line in data_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    counts = {
        "train": sum(item.split is DataSplit.TRAIN for item in records),
        "dev": sum(item.split is DataSplit.DEV for item in records),
        "sealed_test": sum(item.split is DataSplit.SEALED_TEST for item in records),
    }
    if counts != protocol.split_counts:
        raise RuntimeError(f"split counts differ from frozen protocol: {counts}")
    train_records = tuple(item for item in records if item.split is DataSplit.TRAIN)
    dev_records = tuple(item for item in records if item.split is DataSplit.DEV)
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    train_dataset = TokenizedSFTDataset(train_records, tokenizer, protocol.budget.max_length)
    dev_dataset = TokenizedSFTDataset(dev_records, tokenizer, protocol.budget.max_length)

    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    base = AutoModelForCausalLM.from_pretrained(
        args.model_path, local_files_only=True, torch_dtype=torch.bfloat16
    )
    base.config.use_cache = False
    model = get_peft_model(
        base,
        LoraConfig(
            r=protocol.lora.rank,
            lora_alpha=protocol.lora.alpha,
            lora_dropout=protocol.lora.dropout,
            target_modules=protocol.lora.target_modules,
            task_type="CAUSAL_LM",
        ),
    )
    budget = protocol.budget
    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        seed=args.seed,
        data_seed=args.seed,
        bf16=True,
        per_device_train_batch_size=budget.per_device_batch_size,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=budget.gradient_accumulation_steps,
        num_train_epochs=budget.max_epochs,
        max_steps=args.max_steps,
        learning_rate=budget.learning_rate,
        warmup_ratio=budget.warmup_ratio,
        max_grad_norm=budget.max_gradient_norm,
        eval_strategy="steps",
        eval_steps=budget.checkpoint_every_steps,
        save_strategy="steps",
        save_steps=budget.checkpoint_every_steps,
        logging_steps=1,
        save_total_limit=None,
        report_to=[],
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=dev_dataset,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer=tokenizer, padding=True, label_pad_token_id=-100
        ),
    )
    result = trainer.train(
        resume_from_checkpoint=str(args.resume_from) if args.resume_from else None
    )
    trainer.save_state()
    torch.cuda.synchronize()
    eval_loss_by_step = {
        int(item["step"]): float(item["eval_loss"])
        for item in trainer.state.log_history
        if "step" in item and "eval_loss" in item and math.isfinite(float(item["eval_loss"]))
    }
    checkpoints: list[CheckpointEvidence] = []
    for path in sorted(args.output_dir.glob("checkpoint-*"), key=checkpoint_step):
        step = checkpoint_step(path)
        if step in eval_loss_by_step:
            checkpoints.append(
                CheckpointEvidence(path=str(path), step=step, dev_loss=eval_loss_by_step[step])
            )
    state = SeedRunState(
        protocol_version=protocol.protocol_version,
        seed=args.seed,
        status="awaiting_harness_eval",
        completed_optimizer_steps=int(trainer.state.global_step),
        checkpoints=tuple(checkpoints),
    )
    payload = {
        "claim_scope": (
            "screening_only_not_formal_quality"
            if args.max_steps > 0
            else "training_run_requires_executable_dev_and_sealed_evaluation"
        ),
        "protocol": str(args.protocol),
        "protocol_version": protocol.protocol_version,
        "model_revision": protocol.model_revision,
        "dataset_sha256": protocol.train_sha256,
        "seed": args.seed,
        "sealed_records_loaded_into_trainer": 0,
        "run_state": state.model_dump(mode="json"),
        "train_metrics": result.metrics,
        "resources": {
            "wall_time_seconds": round(time.perf_counter() - started, 4),
            "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
            "peak_vram_reserved_mib": round(torch.cuda.max_memory_reserved() / 1024**2, 2),
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
