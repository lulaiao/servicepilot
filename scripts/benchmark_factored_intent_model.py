#!/usr/bin/env python3
"""Offline GPU benchmark for the factored issue/action classifier contract."""

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any

from servicepilot.eval.factored_metrics import factored_metrics
from servicepilot.routing.factored_intent import FactoredIntentResult, project_legacy_intent
from servicepilot.routing.structured_output import build_factored_intent_prompt, parse_factored_intent_output
from servicepilot.training.data_models import DataSplit, SFTTrainingRecord


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--split", choices=("train", "dev", "sealed_test"), default="dev")
    parser.add_argument("--max-examples", type=int)
    parser.add_argument("--max-new-tokens", type=int, default=192)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--dtype", choices=("float32", "float16", "bfloat16"), default="bfloat16")
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260824)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_examples(path: Path, split: DataSplit) -> list[tuple[str, str, FactoredIntentResult]]:
    records = [
        SFTTrainingRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [
        (
            item.record_id,
            item.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1],
            FactoredIntentResult.model_validate_json(item.messages[1]["content"]),
        )
        for item in records
        if item.split is split
    ]


def main() -> None:
    args = parse_args()
    if not args.model_path.is_dir():
        raise SystemExit(f"model path does not exist: {args.model_path}")
    if args.warmup_runs < 0 or args.repetitions <= 0:
        raise SystemExit("warmup must be non-negative and repetitions positive")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else "cpu" if args.device == "auto" else args.device
    if device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda requested but CUDA is unavailable")
    dtype = {"float32": torch.float32, "float16": torch.float16, "bfloat16": torch.bfloat16}[args.dtype]
    torch.manual_seed(args.seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(args.seed)
        torch.cuda.reset_peak_memory_stats()
    examples = load_examples(args.dataset, DataSplit(args.split))
    if args.max_examples is not None:
        if args.max_examples <= 0:
            raise SystemExit("--max-examples must be positive")
        examples = examples[: args.max_examples]
    if not examples:
        raise SystemExit("no examples selected")

    load_started = time.perf_counter()
    print(f"loading model on {device} with {args.dtype}", file=sys.stderr, flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(args.model_path, local_files_only=True, torch_dtype=dtype).to(device)
    if args.adapter_path:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter_path, is_trainable=False)
    model.eval()
    if device == "cuda":
        torch.cuda.synchronize()
    model_load_seconds = time.perf_counter() - load_started

    def prepare(text: str) -> tuple[dict[str, Any], int]:
        rendered = tokenizer.apply_chat_template(
            [{"role": "user", "content": build_factored_intent_prompt(text)}],
            tokenize=False,
            add_generation_prompt=True,
        )
        encoded = tokenizer(rendered, return_tensors="pt")
        inputs = {key: value.to(device) for key, value in encoded.items()}
        return inputs, int(inputs["input_ids"].shape[1])

    def generate(inputs: dict[str, Any]) -> tuple[Any, float]:
        if device == "cuda":
            torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                max_new_tokens=args.max_new_tokens,
            )
        if device == "cuda":
            torch.cuda.synchronize()
        return output, time.perf_counter() - started

    warmup, _ = prepare(examples[0][1])
    for _ in range(args.warmup_runs):
        generate(warmup)
    records = []
    targets = []
    predictions = []
    for index, (example_id, text, target) in enumerate(examples, start=1):
        print(f"example {index}/{len(examples)}: {example_id}", file=sys.stderr, flush=True)
        inputs, input_tokens = prepare(text)
        outputs, latencies = [], []
        for _ in range(args.repetitions):
            output, latency = generate(inputs)
            outputs.append(output)
            latencies.append(latency)
        generated_tokens = int(outputs[0].shape[1]) - input_tokens
        raw = tokenizer.decode(outputs[0][0, input_tokens:], skip_special_tokens=True)
        prediction = None
        error = None
        try:
            prediction = parse_factored_intent_output(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        targets.append(target)
        predictions.append(prediction)
        gold_legacy = project_legacy_intent(target)
        predicted_legacy = project_legacy_intent(prediction) if prediction else None
        records.append({
            "example_id": example_id,
            "gold": target.model_dump(mode="json"),
            "prediction": prediction.model_dump(mode="json") if prediction else None,
            "schema_valid": prediction is not None,
            "issue_correct": prediction is not None and prediction.issue_type is target.issue_type,
            "actions_exact": prediction is not None and set(prediction.requested_actions) == set(target.requested_actions),
            "issue_action_exact": prediction is not None and prediction.issue_type is target.issue_type and set(prediction.requested_actions) == set(target.requested_actions),
            "unrequested_actions": sorted({item.value for item in prediction.requested_actions} - {item.value for item in target.requested_actions}) if prediction else [],
            "gold_legacy_tuple": [gold_legacy.primary_intent.value, *[item.value for item in gold_legacy.secondary_intents]],
            "predicted_legacy_tuple": [predicted_legacy.primary_intent.value, *[item.value for item in predicted_legacy.secondary_intents]] if predicted_legacy else None,
            "latency_seconds": round(sum(latencies) / len(latencies), 4),
            "input_tokens": input_tokens,
            "generated_tokens": generated_tokens,
            "output_consistent_across_repetitions": all(torch.equal(outputs[0], item) for item in outputs[1:]),
            "error": error,
            "raw_output": raw,
        })
    metrics = factored_metrics(targets, predictions)
    report = {
        "candidate": {"path": str(args.model_path.resolve()), "revision": args.revision, "adapter_path": str(args.adapter_path.resolve()) if args.adapter_path else None, "dtype": args.dtype, "device": device, "offline": True},
        "runtime": {"torch_version": torch.__version__, "cuda_runtime": torch.version.cuda, "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"), "gpu_name": torch.cuda.get_device_name(0) if device == "cuda" else None, "seed": args.seed, "warmup_runs": args.warmup_runs, "repetitions": args.repetitions, "max_new_tokens": args.max_new_tokens, "model_load_seconds": round(model_load_seconds, 4)},
        "split": args.split,
        "dataset": str(args.dataset),
        **metrics,
        "mean_latency_seconds": round(sum(item["latency_seconds"] for item in records) / len(records), 4),
        "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 1) if device == "cuda" else None,
        "peak_vram_reserved_mib": round(torch.cuda.max_memory_reserved() / 1024**2, 1) if device == "cuda" else None,
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
