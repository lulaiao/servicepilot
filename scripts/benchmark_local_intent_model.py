#!/usr/bin/env python3
"""Offline, development-split benchmark for a local structured-output model."""

import argparse
import json
import resource
import time
from pathlib import Path
from typing import Any

from servicepilot.eval.routing_dataset import DatasetSplit, build_routing_dataset
from servicepilot.routing.models import IntentResult


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--split", choices=("train", "dev"), default="dev")
    parser.add_argument("--max-examples", type=int)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/local_model_dev.json"),
    )
    return parser.parse_args()


def _json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object found")
    value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("output is not an object")
    return value


def _prompt(text: str) -> str:
    return (
        "你是订单售后分类器。只输出一个JSON对象，不要解释。"
        "primary_intent只能取 order_query,cancel_order,full_refund,"
        "partial_refund,delivery_delay,missing_or_wrong_item,"
        "duplicate_charge,coupon_issue,reschedule,complaint_escalation,"
        "out_of_scope。secondary_intents是数组。slots必须包含order_id、"
        "reason、requested_amount，未知用null。risk_level取low/medium/high；"
        "confidence为0到1；needs_clarification和injection_detected为布尔值。"
        f"\n用户输入：{text}"
    )


def main() -> None:
    args = parse_args()
    if not args.model_path.is_dir():
        raise SystemExit(f"model path does not exist: {args.model_path}")
    # Imported lazily so the deterministic project environment remains small.
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    split = DatasetSplit(args.split)
    examples = [
        item for item in build_routing_dataset() if item.split is split
    ]
    if args.max_examples is not None:
        examples = examples[: args.max_examples]
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_path, local_files_only=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        local_files_only=True,
        torch_dtype=torch.float32,
    )
    model.eval()
    records: list[dict[str, Any]] = []
    for example in examples:
        messages = [{"role": "user", "content": _prompt(example.text)}]
        rendered = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(rendered, return_tensors="pt")
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
        latency = time.perf_counter() - started
        generated = tokenizer.decode(
            output[0, inputs["input_ids"].shape[1] :],
            skip_special_tokens=True,
        )
        error: str | None = None
        prediction: IntentResult | None = None
        try:
            prediction = IntentResult.model_validate(_json_object(generated))
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
                "error": error,
                "raw_output": generated,
            }
        )
    count = len(records)
    report = {
        "candidate": {
            "path": str(args.model_path.resolve()),
            "revision": args.revision,
            "dtype": "float32",
            "device": "cpu",
            "offline": True,
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
