#!/usr/bin/env python3
"""Compare two frozen representations with identical balanced linear heads."""

import argparse
import hashlib
import json
import resource
import statistics
import time
from pathlib import Path

from servicepilot.eval.models import Intent
from servicepilot.training.multilabel_composition_v2_data import (
    MultiLabelCompositionV2Record,
)

LABELS = (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION, Intent.PARTIAL_REFUND)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "mean": round(statistics.mean(values), 4),
        "population_std": round(statistics.pstdev(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def metrics(gold, predicted) -> dict:
    per_label = {}
    f1_values = []
    for index, label in enumerate(LABELS):
        expected, actual = gold[:, index], predicted[:, index]
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
        "per_label": per_label,
        "macro_f1": round(sum(f1_values) / len(f1_values), 4),
        "exact_set_accuracy": round(float((gold == predicted).all(dim=1).float().mean()), 4),
        "complaint_escalation_false_positive_rate": round(
            complaint["false_positive"] / complaint_negatives, 4
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--head-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    dataset = Path(protocol["dataset"])
    if sha256(dataset) != protocol["dataset_sha256"]:
        raise RuntimeError("v2 dataset hash mismatch")
    if tuple(protocol["labels"]) != tuple(label.value for label in LABELS):
        raise RuntimeError("frozen label order changed")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for frozen representation extraction")
    records = tuple(
        MultiLabelCompositionV2Record.model_validate_json(line)
        for line in dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    base = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
    )
    model = PeftModel.from_pretrained(base, Path(protocol["adapter_path"]), is_trainable=False)
    model.eval()
    if any(parameter.requires_grad for parameter in model.parameters()):
        raise RuntimeError("backbone or Adapter is unexpectedly trainable")
    torch.cuda.reset_peak_memory_stats()

    targets = torch.tensor(
        [[label in item.labels for label in LABELS] for item in records], dtype=torch.bool
    )
    train_indices = [index for index, item in enumerate(records) if item.split == "train"]
    dev_indices = [index for index, item in enumerate(records) if item.split == "dev"]
    train_y = targets[train_indices].float()
    dev_y = targets[dev_indices]
    positives = train_y.sum(dim=0)
    pos_weight = (len(train_indices) - positives) / positives
    representation_results = []
    args.head_dir.mkdir(parents=True, exist_ok=True)
    for representation in protocol["representations"]:
        embedding_started = time.perf_counter()
        vectors = []
        with torch.inference_mode():
            for start in range(0, len(records), args.batch_size):
                batch = records[start : start + args.batch_size]
                texts = [representation["input_template"].format(text=item.text) for item in batch]
                encoded = tokenizer(
                    texts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=256,
                ).to("cuda")
                output = model(**encoded, output_hidden_states=True, return_dict=True)
                hidden = output.hidden_states[-1].float()
                if representation["pooling"] == "attention_masked_mean":
                    mask = encoded["attention_mask"].unsqueeze(-1)
                    pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1)
                elif representation["pooling"] == "last_non_padding_token":
                    last = encoded["attention_mask"].sum(dim=1) - 1
                    pooled = hidden[torch.arange(len(batch), device="cuda"), last]
                else:
                    raise RuntimeError(f"unsupported pooling: {representation['pooling']}")
                vectors.extend(torch.nn.functional.normalize(pooled, dim=-1).cpu())
        embedding_seconds = time.perf_counter() - embedding_started
        features = torch.stack(vectors)
        train_x, dev_x = features[train_indices], features[dev_indices]
        seed_results = []
        for seed in protocol["formal_seeds"]:
            torch.manual_seed(seed)
            head = torch.nn.Linear(features.shape[1], len(LABELS))
            optimizer = torch.optim.AdamW(
                head.parameters(),
                lr=protocol["learning_rate"],
                weight_decay=protocol["weight_decay"],
            )
            loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
            for _ in range(protocol["epochs"]):
                optimizer.zero_grad(set_to_none=True)
                loss = loss_fn(head(train_x), train_y)
                if not torch.isfinite(loss):
                    raise RuntimeError("non-finite v2 head loss")
                loss.backward()
                optimizer.step()
            with torch.inference_mode():
                predicted = torch.sigmoid(head(dev_x)) >= protocol["threshold"]
            result = metrics(dev_y, predicted)
            complaint = result["per_label"][Intent.COMPLAINT_ESCALATION.value]
            gates = protocol["acceptance_gates"]
            gate_results = {
                "macro_f1": result["macro_f1"] >= gates["macro_f1_min"],
                "exact_set_accuracy": result["exact_set_accuracy"]
                >= gates["exact_set_accuracy_min"],
                "complaint_escalation_recall": complaint["recall"]
                >= gates["complaint_escalation_recall_min"],
                "complaint_escalation_false_positive": result[
                    "complaint_escalation_false_positive_rate"
                ]
                <= gates["complaint_escalation_false_positive_rate_max"],
            }
            head_path = args.head_dir / f"{representation['id']}_seed{seed}.pt"
            torch.save(
                {
                    "state_dict": head.state_dict(),
                    "input_size": features.shape[1],
                    "labels": protocol["labels"],
                    "threshold": protocol["threshold"],
                    "seed": seed,
                    "representation": representation,
                },
                head_path,
            )
            seed_results.append(
                {
                    "seed": seed,
                    **result,
                    "acceptance_gates": gate_results,
                    "passed": all(gate_results.values()),
                    "head": str(head_path),
                    "head_sha256": sha256(head_path),
                }
            )
        representation_results.append(
            {
                "representation": representation,
                "embedding_seconds": round(embedding_seconds, 4),
                "passed_seed_count": sum(item["passed"] for item in seed_results),
                "metric_summary": {
                    metric: summarize([float(item[metric]) for item in seed_results])
                    for metric in (
                        "macro_f1",
                        "exact_set_accuracy",
                        "complaint_escalation_false_positive_rate",
                    )
                },
                "seed_results": seed_results,
            }
        )
    eligible = [
        item
        for item in representation_results
        if item["passed_seed_count"] == protocol["acceptance_gates"]["required_seed_pass_count"]
    ]
    eligible.sort(
        key=lambda item: (
            -item["metric_summary"]["exact_set_accuracy"]["mean"],
            -item["metric_summary"]["macro_f1"]["mean"],
            item["metric_summary"]["complaint_escalation_false_positive_rate"]["mean"],
            item["embedding_seconds"],
        )
    )
    payload = {
        "schema_version": "servicepilot-multilabel-linear-head-v2-screen-result",
        "protocol": str(args.protocol),
        "protocol_sha256": sha256(args.protocol),
        "dataset_sha256": sha256(dataset),
        "split_counts": {"train": len(train_indices), "dev": len(dev_indices), "sealed_test": 0},
        "pos_weight": [round(float(value), 4) for value in pos_weight],
        "representation_results": representation_results,
        "selected_representation": eligible[0]["representation"]["id"] if eligible else None,
        "any_candidate_passed": bool(eligible),
        "resources": {
            "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 2),
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        },
        "threshold_tuned": False,
        "sealed_accessed": False,
        "claim_scope": "balanced_synthetic_dev_representation_screen",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
