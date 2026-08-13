#!/usr/bin/env python3
"""Audit the development-only structural multi-label comparison."""

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = json.loads(args.result.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if result["protocol_sha256"] != sha256(args.protocol):
        raise RuntimeError("structural result protocol hash mismatch")
    dataset = Path(protocol["dataset"])
    if result["dataset_sha256"] != sha256(dataset):
        raise RuntimeError("structural result dataset hash mismatch")
    if result["threshold_tuned"] or result["sealed_accessed"]:
        raise RuntimeError("development-only no-tuning contract was violated")
    candidates = {item["id"]: item for item in result["candidates"]}
    if set(candidates) != set(protocol["candidates"]):
        raise RuntimeError("result candidates differ from frozen protocol")
    generated = candidates["generative_json"]
    generated_records = generated["records"]
    bare_json_count = sum(item["raw"].strip().startswith("{") for item in generated_records)
    markdown_fence_count = sum("```" in item["raw"] for item in generated_records)
    payload = {
        "schema_version": "servicepilot-multilabel-structural-screen-v1-decision",
        "result": str(args.result),
        "result_sha256": sha256(args.result),
        "protocol_sha256": sha256(args.protocol),
        "example_count": result["example_count"],
        "candidate_summary": {
            name: {
                "schema_valid_rate": item["schema_valid_rate"],
                "macro_f1": item["macro_f1"],
                "exact_set_accuracy": item["exact_set_accuracy"],
                "complaint_escalation_recall": item["per_label"]["complaint_escalation"]["recall"],
                "complaint_escalation_false_positive_rate": item[
                    "complaint_escalation_false_positive_rate"
                ],
                "mean_latency_seconds": item["mean_latency_seconds"],
                "peak_vram_allocated_mib": item["peak_vram_allocated_mib"],
                "passed": item["passed"],
            }
            for name, item in candidates.items()
        },
        "generative_output_contract_audit": {
            "parser_valid_count": round(generated["schema_valid_rate"] * len(generated_records)),
            "bare_json_count": bare_json_count,
            "markdown_fence_count": markdown_fence_count,
            "strict_bare_json_rate": round(bare_json_count / len(generated_records), 4),
            "finding": "lenient_brace_extraction_hides_bare_json_contract_violation",
        },
        "decision": "reject_both_structural_candidates",
        "selected_candidate": None,
        "sealed_v3_allowed": False,
        "agent_integration_allowed": False,
        "next_step": "stop_secondary_intent_enhancement_and_prepare_phase10_delivery",
        "sealed_accessed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
