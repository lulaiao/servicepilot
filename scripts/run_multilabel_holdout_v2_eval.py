#!/usr/bin/env python3
"""One-shot evaluation of the four selected raw-mean heads on sealed v2."""

import argparse
import hashlib
import json
import resource
import time
from collections import defaultdict
from pathlib import Path

from servicepilot.eval.models import Intent
from servicepilot.eval.multilabel_holdout_v2 import MultiLabelHoldoutV2Case

LABELS = (Intent.DELIVERY_DELAY, Intent.COMPLAINT_ESCALATION, Intent.PARTIAL_REFUND)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calculate_metrics(gold, predicted) -> dict:
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
    return {
        "per_label": per_label,
        "macro_f1": round(sum(f1_values) / len(f1_values), 4),
        "exact_set_accuracy": round(float((gold == predicted).all(dim=1).float().mean()), 4),
        "complaint_escalation_false_positive_rate": round(
            complaint["false_positive"] / (len(gold) - complaint["support"]), 4
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--candidate-protocol", type=Path, required=True)
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
    decision_path = Path(protocol["candidate_decision"])
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    candidate_protocol = json.loads(args.candidate_protocol.read_text(encoding="utf-8"))
    if sha256(args.protocol) != freeze["protocol_sha256"]:
        raise RuntimeError("sealed v2 protocol hash mismatch")
    if sha256(decision_path) != protocol["candidate_decision_sha256"]:
        raise RuntimeError("selected candidate decision hash mismatch")
    if sha256(args.candidate_protocol) != decision["protocol_sha256"]:
        raise RuntimeError("candidate training protocol hash mismatch")
    if decision["selected_representation"] != protocol["selected_representation"]:
        raise RuntimeError("selected representation changed after freeze")
    catalog = Path(freeze["catalog"])
    if sha256(catalog) != freeze["catalog_sha256"]:
        raise RuntimeError("sealed v2 catalog hash mismatch")
    expected_heads = {item["sha256"]: item["seed"] for item in decision["selected_heads"]}
    supplied_heads = {sha256(path): path for path in args.heads}
    if set(supplied_heads) != set(expected_heads):
        raise RuntimeError("supplied heads differ from the four selected raw-mean candidates")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for frozen representation extraction")
    cases = tuple(
        MultiLabelHoldoutV2Case.model_validate_json(line)
        for line in catalog.read_text(encoding="utf-8").splitlines()
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
                max_length=256,
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
    category_failures = {}
    for head_hash, path in supplied_heads.items():
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        seed = expected_heads[head_hash]
        if checkpoint["seed"] != seed or checkpoint["threshold"] != protocol["threshold"]:
            raise RuntimeError(f"head metadata mismatch: {path}")
        if checkpoint["representation"]["id"] != protocol["selected_representation"]:
            raise RuntimeError(f"head representation mismatch: {path}")
        head = torch.nn.Linear(checkpoint["input_size"], len(LABELS))
        head.load_state_dict(checkpoint["state_dict"])
        head.eval()
        with torch.inference_mode():
            predicted = torch.sigmoid(head(features)) >= protocol["threshold"]
        result = calculate_metrics(gold, predicted)
        complaint = result["per_label"][Intent.COMPLAINT_ESCALATION.value]
        gate_results = {
            "macro_f1": result["macro_f1"] >= gates["macro_f1_min"],
            "exact_set_accuracy": result["exact_set_accuracy"] >= gates["exact_set_accuracy_min"],
            "complaint_escalation_recall": complaint["recall"]
            >= gates["complaint_escalation_recall_min"],
            "complaint_escalation_false_positive": result[
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
                **result,
                "acceptance_gates": gate_results,
                "passed": all(gate_results.values()),
            }
        )
    results.sort(key=lambda item: item["seed"])
    passed_count = sum(item["passed"] for item in results)
    payload = {
        "schema_version": "servicepilot-multilabel-holdout-v2-result",
        "code_revision": args.code_revision,
        "protocol_sha256": sha256(args.protocol),
        "candidate_decision_sha256": sha256(decision_path),
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
        "claim_scope": "one_shot_independent_multilabel_v2_functional_holdout",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
