#!/usr/bin/env python3
"""Collect Phase 9 resources and apply deterministic no-training gates."""

import argparse
import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path

import torch

from servicepilot.training import TrainingReadinessInput, assess_training_readiness


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument(
        "--data-manifest",
        "--phase8-manifest",
        dest="data_manifest",
        type=Path,
        default=Path("experiments/manifests/phase8_trajectory_dataset_v1.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> None:
    args = parse_args()
    dataset = json.loads(args.data_manifest.read_text(encoding="utf-8"))
    gpu_rows = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,uuid,driver_version,memory.used,memory.total,utilization.gpu",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    gpus = []
    for row in gpu_rows:
        index, name, uuid, driver, used, total, utilization = (
            item.strip() for item in row.split(",")
        )
        gpus.append(
            {
                "index": int(index),
                "name": name,
                "uuid": uuid,
                "driver_version": driver,
                "memory_used_mib": int(used),
                "memory_total_mib": int(total),
                "utilization_percent": int(utilization),
            }
        )
    disk = shutil.disk_usage("/data/ssd1/lla")
    training_views = dataset["training_views"]
    readiness_input = TrainingReadinessInput(
        cuda_available=torch.cuda.is_available(),
        gpu_vram_mib=(
            torch.cuda.get_device_properties(0).total_memory // 1024**2
            if torch.cuda.is_available()
            else 0
        ),
        free_disk_gib=disk.free / 1024**3,
        train_sft_records=dataset["split_counts"]["train"],
        dev_sft_records=dataset["split_counts"]["dev"],
        sealed_sft_records=dataset["split_counts"]["sealed_test"],
        train_preference_records=training_views["preference_split_counts"]["train"],
    )
    packages = {
        name: package_version(name)
        for name in (
            "transformers",
            "datasets",
            "accelerate",
            "peft",
            "trl",
            "bitsandbytes",
            "deepspeed",
            "flash-attn",
        )
    }
    payload = {
        "experiment": "phase9_training_readiness_audit",
        "code_revision": args.code_revision,
        "python": sys.version,
        "runtime": {
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
            "visible_gpu_count": torch.cuda.device_count(),
            "visible_gpu_name": (
                torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
            ),
            "bf16_supported": (
                torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False
            ),
        },
        "gpus": gpus,
        "disk": {
            "path": "/data/ssd1/lla",
            "free_gib": round(disk.free / 1024**3, 2),
            "total_gib": round(disk.total / 1024**3, 2),
        },
        "packages": packages,
        "data_input": {
            "manifest": str(args.data_manifest),
            "canonical_records": dataset["deduplicated_record_count"],
            "sft_split_counts": dataset["split_counts"],
            "preference_records": training_views["preference_record_count"],
            "preference_split_counts": training_views["preference_split_counts"],
        },
        "readiness": [
            item.model_dump(mode="json") for item in assess_training_readiness(readiness_input)
        ],
        "framework_decision": {
            "lora": "provisional_transformers_plus_peft",
            "sft_trainer": "provisional_trl",
            "grpo": "blocked_until_reward_and_data_gates",
            "qlora": "deferred_bitsandbytes_not_installed",
            "distributed": "deferred_single_gpu_smoke_does_not_require_deepspeed",
        },
        "model_decision": {
            "qwen25_0_5b_instruct": "smoke_only_prior_mode_collapse",
            "qwen25_coder_1_5b_instruct": "rejected_for_role_prior_quality_below_rule",
            "qwen25_7b_instruct": "provisional_lora_candidate_after_data_gate",
            "rule_agent": "authoritative_no_training_baseline",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
