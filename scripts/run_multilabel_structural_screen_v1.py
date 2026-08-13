#!/usr/bin/env python3
"""Compare constrained generation and a zero-threshold cross encoder on v2 dev."""

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

from servicepilot.eval.models import Intent
from servicepilot.training.multilabel_composition_v2_data import (
    MultiLabelCompositionV2Record,
)

LABELS = (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION, Intent.PARTIAL_REFUND)
DEFINITIONS = {
    Intent.DELIVERY_DELAY: "当前订单已经超过承诺配送时间或运输进度异常停滞",
    Intent.COMPLAINT_ESCALATION: "用户现在明确要求真人介入、正式投诉、升级或管理人员调查",
    Intent.PARTIAL_REFUND: "用户现在明确要求退回订单中的部分金额、差价或单项费用",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_metrics(gold, predictions, schema_valid: list[bool]) -> dict:
    import torch

    gold_tensor = torch.tensor(gold, dtype=torch.bool)
    predicted_tensor = torch.tensor(predictions, dtype=torch.bool)
    per_label = {}
    f1_values = []
    for index, label in enumerate(LABELS):
        expected, actual = gold_tensor[:, index], predicted_tensor[:, index]
        true_positive = int((expected & actual).sum())
        false_positive = int((~expected & actual).sum())
        false_negative = int((expected & ~actual).sum())
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
        per_label[label.value] = {
            "support": int(expected.sum()),
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    complaint = per_label[Intent.COMPLAINT_ESCALATION.value]
    complaint_negatives = len(gold) - complaint["support"]
    return {
        "schema_valid_rate": round(sum(schema_valid) / len(schema_valid), 4),
        "per_label": per_label,
        "macro_f1": round(sum(f1_values) / len(f1_values), 4),
        "exact_set_accuracy": round(
            float((gold_tensor == predicted_tensor).all(dim=1).float().mean()), 4
        ),
        "complaint_escalation_false_positive_rate": round(
            complaint["false_positive"] / complaint_negatives, 4
        ),
    }


def gate(metrics: dict, gates: dict) -> dict[str, bool]:
    complaint = metrics["per_label"][Intent.COMPLAINT_ESCALATION.value]
    return {
        "schema_valid_rate": metrics["schema_valid_rate"] >= gates["schema_valid_rate_min"],
        "macro_f1": metrics["macro_f1"] >= gates["macro_f1_min"],
        "exact_set_accuracy": metrics["exact_set_accuracy"] >= gates["exact_set_accuracy_min"],
        "complaint_escalation_recall": complaint["recall"]
        >= gates["complaint_escalation_recall_min"],
        "complaint_escalation_false_positive": metrics["complaint_escalation_false_positive_rate"]
        <= gates["complaint_escalation_false_positive_rate_max"],
    }


def parse_generated(text: str) -> tuple[list[bool], bool]:
    try:
        start, end = text.find("{"), text.rfind("}")
        value = json.loads(text[start : end + 1])
        expected_keys = {label.value for label in LABELS}
        invalid_type = any(type(value[key]) is not bool for key in expected_keys)
        if set(value) != expected_keys or invalid_type:
            raise ValueError("invalid exact boolean schema")
        return [value[label.value] for label in LABELS], True
    except (ValueError, TypeError, json.JSONDecodeError):
        return [False] * len(LABELS), False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--generative-model-path", type=Path, required=True)
    parser.add_argument("--cross-encoder-model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    dataset = Path(protocol["dataset"])
    if sha256(dataset) != protocol["dataset_sha256"]:
        raise RuntimeError("structural screen dataset hash mismatch")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoModelForSequenceClassification, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    records = tuple(
        MultiLabelCompositionV2Record.model_validate_json(line)
        for line in dataset.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line)["split"] == protocol["split"]
    )
    gold = [[label in item.labels for label in LABELS] for item in records]
    torch.cuda.reset_peak_memory_stats()

    generator_tokenizer = AutoTokenizer.from_pretrained(
        args.generative_model_path, local_files_only=True
    )
    generator_base = AutoModelForCausalLM.from_pretrained(
        args.generative_model_path,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
    )
    generator = PeftModel.from_pretrained(
        generator_base,
        Path(protocol["candidates"]["generative_json"]["adapter_path"]),
        is_trainable=False,
    )
    generator.eval()
    generated_predictions, generated_valid, generated_records = [], [], []
    generation_started = time.perf_counter()
    for item in records:
        prompt = (
            "判断用户当前明确提出的三个独立诉求。否定、历史行为、未来条件和规则咨询必须为"
            "false。只输出一个JSON对象，必须恰好包含三个布尔字段：delivery_delay、"
            "complaint_escalation、partial_refund。\n用户请求：" + item.text
        )
        rendered = generator_tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
        )
        encoded = generator_tokenizer(rendered, return_tensors="pt").to("cuda")
        started = time.perf_counter()
        with torch.inference_mode():
            output = generator.generate(
                **encoded,
                do_sample=False,
                max_new_tokens=protocol["candidates"]["generative_json"]["max_new_tokens"],
            )
        torch.cuda.synchronize()
        latency = time.perf_counter() - started
        generated_tokens = output[0, encoded["input_ids"].shape[1] :]
        raw = generator_tokenizer.decode(generated_tokens, skip_special_tokens=True)
        prediction, valid = parse_generated(raw)
        generated_predictions.append(prediction)
        generated_valid.append(valid)
        generated_records.append(
            {"record_id": item.record_id, "raw": raw, "latency_seconds": latency}
        )
    generation_seconds = time.perf_counter() - generation_started
    generation_peak = torch.cuda.max_memory_allocated() / 2**20
    del generator, generator_base
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    cross_tokenizer = AutoTokenizer.from_pretrained(
        args.cross_encoder_model_path, local_files_only=True
    )
    cross_encoder = AutoModelForSequenceClassification.from_pretrained(
        args.cross_encoder_model_path,
        local_files_only=True,
        torch_dtype=torch.float16,
    ).to("cuda")
    cross_encoder.eval()
    cross_predictions = []
    cross_started = time.perf_counter()
    pairs = [(item.text, DEFINITIONS[label]) for item in records for label in LABELS]
    scores = []
    with torch.inference_mode():
        for start in range(0, len(pairs), args.batch_size):
            batch = pairs[start : start + args.batch_size]
            encoded = cross_tokenizer(
                [pair[0] for pair in batch],
                [pair[1] for pair in batch],
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="pt",
            ).to("cuda")
            scores.extend(cross_encoder(**encoded).logits.reshape(-1).float().cpu().tolist())
    cross_seconds = time.perf_counter() - cross_started
    threshold = protocol["candidates"]["cross_encoder"]["threshold"]
    for index in range(len(records)):
        start = index * len(LABELS)
        row_scores = scores[start : start + len(LABELS)]
        cross_predictions.append([score >= threshold for score in row_scores])
    cross_peak = torch.cuda.max_memory_allocated() / 2**20

    gates = protocol["acceptance_gates"]
    generated_metrics = compute_metrics(gold, generated_predictions, generated_valid)
    cross_metrics = compute_metrics(gold, cross_predictions, [True] * len(records))
    candidates = [
        {
            "id": "generative_json",
            **generated_metrics,
            "acceptance_gates": gate(generated_metrics, gates),
            "mean_latency_seconds": round(generation_seconds / len(records), 4),
            "peak_vram_allocated_mib": round(generation_peak, 2),
            "records": generated_records,
        },
        {
            "id": "cross_encoder",
            **cross_metrics,
            "acceptance_gates": gate(cross_metrics, gates),
            "mean_latency_seconds": round(cross_seconds / len(records), 4),
            "peak_vram_allocated_mib": round(cross_peak, 2),
            "threshold": threshold,
        },
    ]
    for item in candidates:
        item["passed"] = all(item["acceptance_gates"].values())
    eligible = [item for item in candidates if item["passed"]]
    eligible.sort(
        key=lambda item: (
            -item["exact_set_accuracy"],
            -item["macro_f1"],
            item["complaint_escalation_false_positive_rate"],
            item["mean_latency_seconds"],
            item["peak_vram_allocated_mib"],
        )
    )
    payload = {
        "schema_version": "servicepilot-multilabel-structural-screen-v1-result",
        "protocol_sha256": sha256(args.protocol),
        "dataset_sha256": sha256(dataset),
        "example_count": len(records),
        "candidates": candidates,
        "selected_candidate": eligible[0]["id"] if eligible else None,
        "any_candidate_passed": bool(eligible),
        "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        "threshold_tuned": False,
        "sealed_accessed": False,
        "claim_scope": "balanced_synthetic_dev_structural_screen",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    console_candidates = [
        {key: value for key, value in item.items() if key != "records"} for item in candidates
    ]
    print(json.dumps({**payload, "candidates": console_candidates}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
