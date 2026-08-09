#!/usr/bin/env python3
"""Run resumable Phase 9 checkpoint Harness evaluations across fixed GPUs."""

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--gpus", nargs="+", required=True)
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--steps", nargs="+", type=int, required=True)
    parser.add_argument(
        "--artifact-prefix",
        default="phase9_sft",
        help="Artifact stem before '_seed' (for example phase9_classifier_sft_v3).",
    )
    args = parser.parse_args()
    if re.fullmatch(r"[A-Za-z0-9_-]+", args.artifact_prefix) is None:
        parser.error("--artifact-prefix may contain only letters, digits, '_' and '-'")
    return args


async def run_job(
    gpu: str,
    model_path: Path,
    revision: str,
    artifact_prefix: str,
    seed: int,
    step: int,
) -> None:
    run_stem = f"{artifact_prefix}_seed{seed}"
    checkpoint = Path(f"artifacts/checkpoints/{run_stem}/checkpoint-{step}")
    report = Path(f"artifacts/reports/{run_stem}_checkpoint{step}_dev_harness.json")
    trace = Path(f"artifacts/traces/{run_stem}_checkpoint{step}_dev_harness.json")
    log = Path(f"artifacts/logs/{run_stem}_checkpoint{step}_dev_harness.log")
    if report.exists():
        print(f"skip existing seed={seed} step={step}", flush=True)
        return
    if not checkpoint.exists():
        raise RuntimeError(f"missing checkpoint: {checkpoint}")
    report.parent.mkdir(parents=True, exist_ok=True)
    trace.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "scripts/run_phase4_agent_model_eval.py",
        "--model-path",
        str(model_path),
        "--adapter-path",
        str(checkpoint),
        "--revision",
        revision,
        "--device",
        "cuda",
        "--dtype",
        "bfloat16",
        "--seed",
        str(seed),
        "--evaluation-split",
        "dev",
        "--output",
        str(report),
        "--trace-output",
        str(trace),
    ]
    environment = os.environ.copy()
    environment["CUDA_VISIBLE_DEVICES"] = gpu
    environment["HF_HUB_OFFLINE"] = "1"
    environment["TRANSFORMERS_OFFLINE"] = "1"
    environment["PYTHONPATH"] = "src"
    print(f"start gpu={gpu} seed={seed} step={step}", flush=True)
    with log.open("wb") as handle:
        process = await asyncio.create_subprocess_exec(
            *command, stdout=handle, stderr=asyncio.subprocess.STDOUT, env=environment
        )
        return_code = await process.wait()
    if return_code != 0 or not report.exists():
        raise RuntimeError(
            f"Harness failed gpu={gpu} seed={seed} step={step}; see {log}"
        )
    print(f"done gpu={gpu} seed={seed} step={step}", flush=True)


async def worker(
    gpu: str,
    queue: asyncio.Queue[tuple[int, int]],
    model_path: Path,
    revision: str,
    artifact_prefix: str,
    failures: list[str],
) -> None:
    while not queue.empty():
        try:
            seed, step = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        try:
            await run_job(gpu, model_path, revision, artifact_prefix, seed, step)
        except RuntimeError as exc:
            failures.append(str(exc))
            print(f"failed {exc}", flush=True)
        finally:
            queue.task_done()


async def main_async() -> None:
    args = parse_args()
    queue: asyncio.Queue[tuple[int, int]] = asyncio.Queue()
    for seed in args.seeds:
        for step in args.steps:
            queue.put_nowait((seed, step))
    failures: list[str] = []
    await asyncio.gather(
        *(
            worker(
                gpu,
                queue,
                args.model_path,
                args.revision,
                args.artifact_prefix,
                failures,
            )
            for gpu in args.gpus
        )
    )
    if failures:
        raise RuntimeError("; ".join(failures))


if __name__ == "__main__":
    asyncio.run(main_async())
