#!/usr/bin/env python3
"""Offline, development-split benchmark for a local structured-output model."""

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any

from servicepilot.eval.routing_dataset import DatasetSplit, build_routing_dataset
from servicepilot.routing.structured_output import (
    build_intent_prompt,
    parse_intent_output,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--split", choices=("train", "dev"), default="dev")
    parser.add_argument("--max-examples", type=int)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument(
        "--device", choices=("auto", "cpu", "cuda"), default="auto"
    )
    parser.add_argument(
        "--dtype",
        choices=("float32", "float16", "bfloat16"),
        default="float16",
    )
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/local_model_dev.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.model_path.is_dir():
        raise SystemExit(f"model path does not exist: {args.model_path}")
    # Imported lazily so the deterministic project environment remains small.
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if args.warmup_runs < 0:
        raise SystemExit("--warmup-runs must be non-negative")
    if args.repetitions <= 0:
        raise SystemExit("--repetitions must be positive")
    if args.max_examples is not None and args.max_examples <= 0:
        raise SystemExit("--max-examples must be positive")
    device = (
        "cuda"
        if args.device == "auto" and torch.cuda.is_available()
        else "cpu"
        if args.device == "auto"
        else args.device
    )
    if device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda requested but CUDA is unavailable")
    dtype = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }[args.dtype]
    torch.manual_seed(args.seed)
    if device == "cuda":
        torch.cuda.manual_seed_all(args.seed)
        torch.cuda.reset_peak_memory_stats()

    split = DatasetSplit(args.split)
    examples = [
        item for item in build_routing_dataset() if item.split is split
    ]
    if args.max_examples is not None:
        examples = examples[: args.max_examples]
    load_started = time.perf_counter()
    print(f"loading model on {device} with {args.dtype}", file=sys.stderr, flush=True)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path, local_files_only=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        local_files_only=True,
        torch_dtype=dtype,
    ).to(device)
    model.eval()
    if device == "cuda":
        torch.cuda.synchronize()
    model_load_seconds = time.perf_counter() - load_started
    print(
        f"model loaded in {model_load_seconds:.3f}s",
        file=sys.stderr,
        flush=True,
    )

    def prepare(text: str) -> tuple[dict[str, Any], int]:
        messages = [{"role": "user", "content": build_intent_prompt(text)}]
        rendered = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
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

    if examples:
        warmup_inputs, _ = prepare(examples[0].text)
        for warmup_index in range(args.warmup_runs):
            print(
                f"warmup {warmup_index + 1}/{args.warmup_runs}",
                file=sys.stderr,
                flush=True,
            )
            generate(warmup_inputs)

    records: list[dict[str, Any]] = []
    for example_index, example in enumerate(examples, start=1):
        print(
            f"example {example_index}/{len(examples)}: {example.example_id}",
            file=sys.stderr,
            flush=True,
        )
        inputs, input_tokens = prepare(example.text)
        outputs: list[Any] = []
        latencies: list[float] = []
        for _ in range(args.repetitions):
            output, latency = generate(inputs)
            outputs.append(output)
            latencies.append(latency)
        output = outputs[0]
        latency = sum(latencies) / len(latencies)
        generated_tokens = int(output.shape[1]) - input_tokens
        generated = tokenizer.decode(
            output[0, input_tokens:],
            skip_special_tokens=True,
        )
        error: str | None = None
        prediction = None
        try:
            prediction = parse_intent_output(generated)
        except (ValueError, json.JSONDecodeError) as exc:
            error = f"{type(exc).__name__}: {exc}"
        records.append(
            {
                "example_id": example.example_id,
                "gold_primary": example.primary_intent.value,
                "prediction": (
                    prediction.model_dump(mode="json") if prediction else None
                ),
                "schema_valid": prediction is not None,
                "primary_correct": (
                    prediction is not None
                    and prediction.primary_intent is example.primary_intent
                ),
                "latency_seconds": round(latency, 4),
                "latency_repetitions_seconds": [
                    round(item, 4) for item in latencies
                ],
                "input_tokens": input_tokens,
                "generated_tokens": generated_tokens,
                "generation_tokens_per_second": round(
                    generated_tokens / latency, 4
                ),
                "output_consistent_across_repetitions": all(
                    torch.equal(outputs[0], item) for item in outputs[1:]
                ),
                "error": error,
                "raw_output": generated,
            }
        )
    count = len(records)
    report = {
        "candidate": {
            "path": str(args.model_path.resolve()),
            "revision": args.revision,
            "dtype": args.dtype,
            "device": device,
            "offline": True,
        },
        "runtime": {
            "torch_version": torch.__version__,
            "cuda_runtime": torch.version.cuda,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "gpu_name": (
                torch.cuda.get_device_name(0) if device == "cuda" else None
            ),
            "seed": args.seed,
            "warmup_runs": args.warmup_runs,
            "repetitions": args.repetitions,
            "max_new_tokens": args.max_new_tokens,
            "batch_size": 1,
            "do_sample": False,
            "model_load_seconds": round(model_load_seconds, 4),
        },
        "split": split.value,
        "example_count": count,
        "schema_valid_rate": round(
            sum(item["schema_valid"] for item in records) / count, 4
        ),
        "primary_accuracy": round(
            sum(item["primary_correct"] for item in records) / count, 4
        ),
        "mean_latency_seconds": round(
            sum(item["latency_seconds"] for item in records) / count, 4
        ),
        "peak_rss_mib": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1
        ),
        "peak_vram_allocated_mib": (
            round(torch.cuda.max_memory_allocated() / 1024**2, 1)
            if device == "cuda"
            else None
        ),
        "peak_vram_reserved_mib": (
            round(torch.cuda.max_memory_reserved() / 1024**2, 1)
            if device == "cuda"
            else None
        ),
        "mean_generation_tokens_per_second": round(
            sum(item["generated_tokens"] for item in records)
            * args.repetitions
            / sum(
                sum(item["latency_repetitions_seconds"])
                for item in records
            ),
            4,
        ),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, indent=2))


if __name__ == "__main__":
    main()
