# ADR 0010: Gate training by local evidence before selecting a stack

- Status: Accepted for Phase 9A
- Date: 2026-08-08

## Context

ServicePilot has GPU access and cached models, but resource availability alone
does not justify post-training. Phase 4 showed that Qwen2.5-7B improved a small
component metric yet reduced executable task success from 1.0 to 0.8889 and
introduced policy and false-success errors. Phase 8 currently provides only 24
train SFT records and 33 train preference pairs.

## Local audit

The host exposes eight RTX A6000 48GB cards. GPUs 4 and 5 were idle during the
audit. A real 2 MiB FP16 allocation on GPU 4 passed with PyTorch 2.5.1+cu121;
BF16 is supported. The data filesystem has 3,402.98 GiB free. CUDA and disk are
therefore not current blockers.

Installed candidates are Transformers 4.47.1, Datasets 3.2.0, Accelerate 1.2.1,
PEFT 0.14.0, and TRL 0.14.0. Both `SFTTrainer` and `GRPOTrainer` import. Neither
bitsandbytes, DeepSpeed, nor FlashAttention is installed.

## Decision

Use direct Transformers plus PEFT as the provisional LoRA smoke path because it
is already installed, exposes the adapter configuration directly, and does not
require a distributed abstraction. TRL remains provisional for standardized
SFT/GRPO loops, but API import is not acceptance evidence. Defer QLoRA,
DeepSpeed, and FlashAttention: a single A6000 smoke run does not yet demonstrate
a need for quantized loading, sharding, or custom attention kernels.

Keep the rule Agent as the authoritative baseline. Qwen2.5-0.5B-Instruct may be
used only for a cheap pipeline smoke test because it mode-collapsed in Phase 4.
Reject the cached Coder 1.5B for this role. Keep Qwen2.5-7B-Instruct as a
provisional LoRA research candidate only after the data gate, because it is the
strongest measured local instruction candidate but currently loses end-to-end.

## Project gates

These thresholds are ServicePilot evidence policy, not universal machine-
learning minima:

- LoRA smoke: working CUDA, at least 40 GiB VRAM, and 100 GiB free disk.
- Reportable LoRA SFT: at least 500 train, 100 dev, and 100 sealed SFT records.
- GRPO: all SFT gates, at least 500 train preference records, passing reward
  unit tests, reward-distribution audit, and reward-hacking audit.

Only LoRA smoke currently passes. Formal SFT and both GRPO variants are blocked.
No training improvement may be claimed from a smoke run.

## Updated data decision

The admitted expanded dataset now contains 696/126/120 SFT records across
232/42/40 semantic families and 1,011 train preference pairs. A new readiness
audit therefore advances LoRA SFT from blocked to allowed. GRPO remains blocked
because reward unit tests, distribution audit, and reward-hacking audit do not
exist. This update changes readiness only; Qwen2.5-7B remains provisional until
a frozen, repeated LoRA experiment beats its untrained executable baseline.
