#!/usr/bin/env python3
"""Train a tiny BCE multi-label head over frozen shared-model representations."""

import argparse
import hashlib
import json
import math
import resource
import time
from pathlib import Path

from servicepilot.eval.models import Intent
from servicepilot.training.multilabel_composition_data import MultiLabelCompositionRecord


LABELS = (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION, Intent.PARTIAL_REFUND)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--head-output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    data_path = Path(protocol["dataset"])
    if sha256(data_path) != protocol["dataset_sha256"]:
        raise RuntimeError("dataset hash mismatch")
    if tuple(protocol["labels"]) != tuple(label.value for label in LABELS):
        raise RuntimeError("label order differs from frozen protocol")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for frozen representation extraction")
    seed = int(args.seed if args.seed is not None else protocol["screening_seed"])
    if seed not in protocol["formal_seeds"]:
        raise RuntimeError("seed is not declared in the frozen protocol")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    records = tuple(
        MultiLabelCompositionRecord.model_validate_json(line)
        for line in data_path.read_text(encoding="utf-8").splitlines()
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
    model = PeftModel.from_pretrained(
        base, Path(protocol["adapter_path"]), is_trainable=False
    )
    model.eval()
    if any(parameter.requires_grad for parameter in model.parameters()):
        raise RuntimeError("backbone or adapter is unexpectedly trainable")

    torch.cuda.reset_peak_memory_stats()
    embedding_started = time.perf_counter()
    vectors = []
    with torch.inference_mode():
        for start in range(0, len(records), args.batch_size):
            batch = records[start : start + args.batch_size]
            encoded = tokenizer(
                [item.text for item in batch],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128,
            ).to("cuda")
            output = model(**encoded, output_hidden_states=True, return_dict=True)
            hidden = output.hidden_states[-1].float()
            mask = encoded["attention_mask"].unsqueeze(-1)
            pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1)
            vectors.extend(torch.nn.functional.normalize(pooled, dim=-1).cpu())
            del output, hidden, pooled, encoded
    embedding_seconds = time.perf_counter() - embedding_started
    del model, base
    torch.cuda.empty_cache()

    features = torch.stack(vectors)
    targets = torch.tensor(
        [[float(label in item.labels) for label in LABELS] for item in records],
        dtype=torch.float32,
    )
    train_indices = [index for index, item in enumerate(records) if item.split == "train"]
    dev_indices = [index for index, item in enumerate(records) if item.split == "dev"]
    train_x, train_y = features[train_indices], targets[train_indices]
    dev_x, dev_y = features[dev_indices], targets[dev_indices]
    positives = train_y.sum(dim=0)
    pos_weight = (len(train_indices) - positives) / positives

    head = torch.nn.Linear(features.shape[1], len(LABELS))
    optimizer = torch.optim.AdamW(
        head.parameters(),
        lr=float(protocol["learning_rate"]),
        weight_decay=float(protocol["weight_decay"]),
    )
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    losses = []
    training_started = time.perf_counter()
    for epoch in range(1, int(protocol["epochs"]) + 1):
        optimizer.zero_grad(set_to_none=True)
        loss = loss_fn(head(train_x), train_y)
        if not torch.isfinite(loss):
            raise RuntimeError("non-finite loss")
        loss.backward()
        optimizer.step()
        if epoch in {1, 10, 25, 50, 100, int(protocol["epochs"])}:
            losses.append({"epoch": epoch, "train_loss": float(loss.detach())})
    training_seconds = time.perf_counter() - training_started

    with torch.inference_mode():
        probabilities = torch.sigmoid(head(dev_x))
    predicted = probabilities >= float(protocol["threshold"])
    gold = dev_y.bool()
    per_label = {}
    f1_values = []
    for index, label in enumerate(LABELS):
        g, p = gold[:, index], predicted[:, index]
        tp = int((g & p).sum())
        fp = int((~g & p).sum())
        fn = int((g & ~p).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_label[label.value] = {
            "support": int(g.sum()),
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    complaint = per_label[Intent.COMPLAINT_ESCALATION.value]
    complaint_negatives = len(dev_indices) - complaint["support"]
    complaint_fp_rate = complaint["false_positive"] / complaint_negatives
    exact = float((predicted == gold).all(dim=1).float().mean())
    macro_f1 = sum(f1_values) / len(f1_values)
    gates = protocol["acceptance_gates"]
    gate_results = {
        "complaint_escalation_false_positive": complaint_fp_rate
        <= gates["complaint_escalation_false_positive_rate_max"],
        "complaint_escalation_recall": complaint["recall"]
        >= gates["complaint_escalation_recall_min"],
        "macro_f1": macro_f1 >= gates["macro_f1_min"],
        "exact_set_accuracy": exact >= gates["exact_set_accuracy_min"],
    }
    args.head_output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": head.state_dict(),
            "labels": [label.value for label in LABELS],
            "input_size": features.shape[1],
            "threshold": protocol["threshold"],
            "seed": seed,
        },
        args.head_output,
    )
    payload = {
        "schema_version": "servicepilot-multilabel-linear-head-v1-screen-result",
        "protocol": str(args.protocol),
        "protocol_sha256": sha256(args.protocol),
        "dataset_sha256": sha256(data_path),
        "model_revision": protocol["model_revision"],
        "seed": seed,
        "split_counts": {"train": len(train_indices), "dev": len(dev_indices), "sealed_test": 0},
        "head_parameter_count": sum(parameter.numel() for parameter in head.parameters()),
        "pos_weight": [round(float(value), 6) for value in pos_weight],
        "losses": losses,
        "per_label": per_label,
        "macro_f1": round(macro_f1, 4),
        "exact_set_accuracy": round(exact, 4),
        "complaint_escalation_false_positive_rate": round(complaint_fp_rate, 4),
        "acceptance_gates": gate_results,
        "passed": all(gate_results.values()),
        "head_output": str(args.head_output),
        "head_sha256": sha256(args.head_output),
        "resources": {
            "embedding_seconds": round(embedding_seconds, 4),
            "head_training_seconds": round(training_seconds, 4),
            "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 2),
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        },
        "threshold_tuned_on_dev": False,
        "sealed_accessed": False,
        "claim_scope": "single_seed_synthetic_pilot_screen",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
