# Phase 9C LoRA SFT runbook

## Scope

The runner trains one predeclared seed at a time, loads only train/dev records,
saves resumable PEFT checkpoints every 25 optimizer steps, and records dev loss.
It intentionally does not choose a checkpoint until every candidate has an
executable dev Harness report. The sealed split is not loaded into Trainer.

The one-step control run passed on RTX A6000 GPU 4 with 16-example gradient
accumulation. It used 22,346.19 MiB peak allocated and 23,318 MiB peak reserved
VRAM. This validates the formal Trainer path only.

## Formal seed command

Run once for each frozen seed `20260808`, `20260809`, `20260810`, and
`20260811`, changing the GPU and seed-specific paths. Do not add `--max-steps`:

```bash
cd /data/ssd1/lla/servicepilot
CUDA_VISIBLE_DEVICES=4 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=src \
/data/ssd1/lla/conda_envs/mcp-sql-reflex-rl/bin/python \
scripts/run_phase9_lora_sft_seed.py \
  --protocol experiments/configs/phase9_qwen25_7b_lora_sft_v1.json \
  --model-path /data/ssd1/lla/cache/servicepilot-hf/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28 \
  --output-dir artifacts/checkpoints/phase9_sft_seed20260808 \
  --report artifacts/reports/phase9_sft_seed20260808.json \
  --seed 20260808
```

To resume, repeat the exact command and add, for example,
`--resume-from artifacts/checkpoints/phase9_sft_seed20260808/checkpoint-75`.
Never resume a seed from another seed's directory.

## Checkpoint evaluation and selection

Evaluate each saved adapter through `run_phase4_agent_model_eval.py` with
`--adapter-path CHECKPOINT --evaluation-split dev`. Then pass all reports for
that seed as repeated `--harness-report` arguments to
`select_phase9_sft_checkpoint.py`. Selection fails closed if any checkpoint is
missing evidence or if no checkpoint has zero high-risk errors.

The existing Phase 3 executable catalog is development evidence, not a sealed
final set. A separately frozen executable sealed catalog must be implemented
before any final quality claim.
