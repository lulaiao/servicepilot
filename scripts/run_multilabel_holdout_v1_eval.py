#!/usr/bin/env python3
"""Run the frozen multi-label holdout once for all four predeclared heads."""

import argparse
import hashlib
import json
import resource
import time
from collections import defaultdict
from pathlib import Path

from servicepilot.eval.models import Intent
from servicepilot.eval.multilabel_holdout_v1 import MultiLabelHoldoutCase

LABELS = (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION, Intent.PARTIAL_REFUND)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calculate_metrics(gold, predicted) -> dict:
    per_label = {}
    f1_values = []
    for index, label in enumerate(LABELS):
        expected = gold[:, index]
        actual = predicted[:, index]
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
    exact = float((gold == predicted).all(dim=1).float().mean())
    return {
        "per_label": per_label,
        "macro_f1": round(sum(f1_values) / len(f1_values), 4),
        "exact_set_accuracy": round(exact, 4),
        "complaint_escalation_false_positive_rate": round(
            complaint["false_positive"] / complaint_negatives, 4
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--formal-manifest", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--heads", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("one-shot output already exists; rerun is forbidden")

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    freeze = json.loads(args.freeze_manifest.read_text(encoding="utf-8"))
    formal = json.loads(args.formal_manifest.read_text(encoding="utf-8"))
    if sha256(args.protocol) != freeze["protocol_sha256"]:
        raise RuntimeError("sealed protocol hash mismatch")
    if sha256(Path(protocol["candidate_protocol"])) != protocol["candidate_protocol_sha256"]:
        raise RuntimeError("candidate protocol hash mismatch")
    catalog = Path(freeze["catalog"])
    if sha256(catalog) != freeze["catalog_sha256"]:
        raise RuntimeError("sealed catalog hash mismatch")
    if protocol["threshold"] != 0.5 or protocol["threshold_tuning_allowed"]:
        raise RuntimeError("frozen threshold contract changed")
    if tuple(protocol["head_seeds"]) != tuple(formal["seeds"]):
        raise RuntimeError("formal seed set differs from sealed protocol")
    expected_heads = {item["head_sha256"]: item["seed"] for item in formal["runs"]}
    supplied_heads = {sha256(path): path for path in args.heads}
    if set(supplied_heads) != set(expected_heads):
        raise RuntimeError("supplied head hashes differ from the four accepted candidates")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for frozen representation extraction")
    cases = tuple(
        MultiLabelHoldoutCase.model_validate_json(line)
        for line in catalog.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    candidate_protocol = json.loads(
        Path(protocol["candidate_protocol"]).read_text(encoding="utf-8")
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
        base, Path(candidate_protocol["adapter_path"]), is_trainable=False
    )
    model.eval()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    vectors = []
    with torch.inference_mode():
        for start in range(0, len(cases), args.batch_size):
            batch = cases[start : start + args.batch_size]
            encoded = tokenizer(
                [case.text for case in batch],
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
    embedding_seconds = time.perf_counter() - started
    features = torch.stack(vectors)
    gold = torch.tensor(
        [[label in case.labels for label in LABELS] for case in cases], dtype=torch.bool
    )
    gates = protocol["acceptance_gates"]
    results = []
    category_failures: dict[str, dict[str, int]] = defaultdict(dict)
    for head_hash, path in supplied_heads.items():
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        seed = expected_heads[head_hash]
        if checkpoint["seed"] != seed or checkpoint["threshold"] != protocol["threshold"]:
            raise RuntimeError(f"head metadata mismatch: {path}")
        head = torch.nn.Linear(checkpoint["input_size"], len(LABELS))
        head.load_state_dict(checkpoint["state_dict"])
        head.eval()
        with torch.inference_mode():
            predicted = torch.sigmoid(head(features)) >= protocol["threshold"]
        metrics = calculate_metrics(gold, predicted)
        complaint = metrics["per_label"][Intent.COMPLAINT_ESCALATION.value]
        gate_results = {
            "macro_f1": metrics["macro_f1"] >= gates["macro_f1_min"],
            "exact_set_accuracy": metrics["exact_set_accuracy"] >= gates["exact_set_accuracy_min"],
            "complaint_escalation_recall": complaint["recall"]
            >= gates["complaint_escalation_recall_min"],
            "complaint_escalation_false_positive": metrics[
                "complaint_escalation_false_positive_rate"
            ]
            <= gates["complaint_escalation_false_positive_rate_max"],
        }
        failures = defaultdict(int)
        for index, case in enumerate(cases):
            if not bool((predicted[index] == gold[index]).all()):
                failures[case.category] += 1
        category_failures[str(seed)] = dict(sorted(failures.items()))
        results.append(
            {
                "seed": seed,
                "head_sha256": head_hash,
                **metrics,
                "acceptance_gates": gate_results,
                "passed": all(gate_results.values()),
            }
        )
    results.sort(key=lambda item: item["seed"])
    passed_count = sum(item["passed"] for item in results)
    payload = {
        "schema_version": "servicepilot-multilabel-holdout-v1-result",
        "code_revision": args.code_revision,
        "protocol": str(args.protocol),
        "protocol_sha256": sha256(args.protocol),
        "catalog_sha256": sha256(catalog),
        "case_count": len(cases),
        "seed_results": results,
        "category_failure_counts": category_failures,
        "passed_seed_count": passed_count,
        "required_seed_pass_count": protocol["required_seed_pass_count"],
        "passed": passed_count == protocol["required_seed_pass_count"],
        "resources": {
            "shared_embedding_seconds": round(embedding_seconds, 4),
            "peak_vram_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 2),
            "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2),
        },
        "threshold_tuned": False,
        "selection_or_tuning_allowed": False,
        "rerun_allowed": False,
        "claim_scope": "one_shot_independent_multilabel_functional_holdout",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    console_payload = {
        key: value for key, value in payload.items() if key != "category_failure_counts"
    }
    print(json.dumps(console_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
