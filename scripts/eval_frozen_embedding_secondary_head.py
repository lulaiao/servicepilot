#!/usr/bin/env python3
"""Evaluate a fixed secondary head over frozen shared-model representations."""

import argparse
import hashlib
import json
import resource
import time
from pathlib import Path

from servicepilot.eval.composition_adversarial import build_composition_adversarial_v1
from servicepilot.eval.models import Intent, ScenarioSpec
from servicepilot.training.classifier_data import classifier_target
from servicepilot.training.classifier_v5_data import build_classifier_v5_sft
from servicepilot.training.data_models import DataSplit


def utterance(record: object) -> str:
    return record.messages[0]["content"].rsplit("用户输入：", maxsplit=1)[-1]


def metric(gold: list[bool], predicted: list[bool]) -> dict[str, float | int]:
    tp = sum(g and p for g, p in zip(gold, predicted, strict=True))
    fp = sum(not g and p for g, p in zip(gold, predicted, strict=True))
    fn = sum(g and not p for g, p in zip(gold, predicted, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "count": len(gold),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "accuracy": round(sum(g == p for g, p in zip(gold, predicted, strict=True)) / len(gold), 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--model-report", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for frozen embedding evaluation")
    torch.manual_seed(20260811)
    torch.cuda.manual_seed_all(20260811)
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
    )
    model = PeftModel.from_pretrained(base, args.adapter_path, is_trainable=False)
    model.eval()

    train_examples: list[tuple[str, bool]] = []
    for record in build_classifier_v5_sft():
        if record.split is not DataSplit.TRAIN:
            continue
        target = json.loads(record.messages[1]["content"])
        if target["primary_intent"] == Intent.DELIVERY_DELAY.value:
            train_examples.append(
                (
                    utterance(record),
                    Intent.COMPLAINT_ESCALATION.value in target["secondary_intents"],
                )
            )
    augmented_examples = list(train_examples)
    for case in build_composition_adversarial_v1():
        if case.model_primary is not Intent.DELIVERY_DELAY:
            continue
        if case.category in {"explicit_pair", "three_intent"}:
            augmented_examples.append((case.text, True))
        elif case.category in {
            "negated_escalation",
            "conditional_future",
            "historical_request",
            "delivery_only",
        }:
            augmented_examples.append((case.text, False))

    scenarios = tuple(
        ScenarioSpec.model_validate_json(line)
        for line in args.catalog.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    source = json.loads(args.model_report.read_text(encoding="utf-8"))
    model_records = source["learned_extractor_agent"]["classifier_records"]
    dev_examples = []
    for scenario, record in zip(scenarios, model_records, strict=True):
        prediction = record["prediction"]
        if prediction["primary_intent"] != Intent.DELIVERY_DELAY.value:
            continue
        target = classifier_target(scenario)
        dev_examples.append(
            (
                scenario.scenario_id,
                scenario.user_utterance,
                Intent.COMPLAINT_ESCALATION in target.secondary_intents,
                Intent.COMPLAINT_ESCALATION.value in prediction["secondary_intents"],
            )
        )

    texts = list(dict.fromkeys(
        [text for text, _ in augmented_examples] + [text for _, text, _, _ in dev_examples]
    ))
    embeddings: dict[str, torch.Tensor] = {}
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(texts), args.batch_size):
            batch = texts[start : start + args.batch_size]
            encoded = tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128,
            ).to("cuda")
            output = model(**encoded, output_hidden_states=True, return_dict=True)
            hidden = output.hidden_states[-1].float()
            mask = encoded["attention_mask"].unsqueeze(-1)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1)
            pooled = torch.nn.functional.normalize(pooled, dim=-1).cpu()
            for text, vector in zip(batch, pooled, strict=True):
                embeddings[text] = vector
            del output, hidden, pooled, encoded
    embedding_seconds = time.perf_counter() - started

    def centroid(examples: list[tuple[str, bool]], label: bool) -> torch.Tensor:
        values = torch.stack([embeddings[text] for text, value in examples if value is label])
        return torch.nn.functional.normalize(values.mean(dim=0), dim=0)

    def predict(examples: list[tuple[str, bool]], text: str) -> tuple[bool, float]:
        positive = centroid(examples, True)
        negative = centroid(examples, False)
        vector = embeddings[text]
        margin = float(torch.dot(vector, positive) - torch.dot(vector, negative))
        return margin > 0, margin

    gold = [value for _, _, value, _ in dev_examples]
    generated = [value for _, _, _, value in dev_examples]
    base_predictions = [predict(train_examples, text) for _, text, _, _ in dev_examples]
    augmented_predictions = [
        predict(augmented_examples, text) for _, text, _, _ in dev_examples
    ]
    payload = {
        "schema_version": "servicepilot-frozen-embedding-secondary-head-v1",
        "candidate": {
            "model_path": str(args.model_path),
            "revision": args.revision,
            "adapter_path": str(args.adapter_path),
            "dtype": "bfloat16",
            "pooling": "last_hidden_attention_masked_mean",
            "head": "positive_negative_normalized_centroid_fixed_zero_margin",
        },
        "base_train_count": len(train_examples),
        "augmented_train_count": len(augmented_examples),
        "dev_count": len(dev_examples),
        "generative_secondary": metric(gold, generated),
        "base_frozen_embedding_head": metric(gold, [value for value, _ in base_predictions]),
        "augmented_frozen_embedding_head": metric(
            gold, [value for value, _ in augmented_predictions]
        ),
        "records": [
            {
                "scenario_id": scenario_id,
                "gold": target,
                "generative": generative,
                "base_head": base_predictions[index][0],
                "base_margin": round(base_predictions[index][1], 6),
                "augmented_head": augmented_predictions[index][0],
                "augmented_margin": round(augmented_predictions[index][1], 6),
            }
            for index, (scenario_id, _, target, generative) in enumerate(dev_examples)
        ],
        "resources": {
            "embedding_seconds": round(embedding_seconds, 4),
            "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 2),
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        },
        "model_report_sha256": hashlib.sha256(args.model_report.read_bytes()).hexdigest(),
        "catalog_sha256": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        "threshold_tuned_on_dev": False,
        "sealed_accessed": False,
        "claim_scope": "reused_dev_representation_screen",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
