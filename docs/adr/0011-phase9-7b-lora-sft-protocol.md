# ADR 0011: Freeze the 7B LoRA SFT protocol before quality training

- Status: Accepted for Phase 9B dry-run; formal experiment pending
- Date: 2026-08-08

## Context

The expanded dataset passes the declared SFT size and isolation gates, and the
0.5B smoke test established basic PEFT plumbing. That does not establish that
the selected 7B model fits the real sequence budget, that its optimizer state
can be resumed, or that a later quality comparison is protected from
test-guided tuning.

## Decision

Freeze the model revision, dataset hash, four seeds, BF16 precision, LoRA
targets and rank, training budget, checkpoint cadence, dev selection order, and
sealed-test policy in
`experiments/configs/phase9_qwen25_7b_lora_sft_v1.json`. Checkpoints must first
have zero dev high-risk errors, then maximize dev task success, then minimize
dev loss. The sealed split is excluded from selection and may be evaluated once
per predeclared final seed after the configuration freeze.

Use direct Transformers plus PEFT for the bounded feasibility run. The real
7B/BF16 dry-run completed a 734-token forward/backward optimizer step with
20,892.78 MiB peak allocated VRAM and 21,594 MiB peak reserved VRAM. Adapter and
optimizer reload both succeeded.

## Consequences

The 7B training path is technically feasible on one RTX A6000 without QLoRA,
DeepSpeed, or FlashAttention, so those components remain unjustified. The
dry-run is not a quality experiment: its single loss value cannot support an
improvement claim. Formal SFT still requires all four frozen seeds, dev-only
checkpoint selection, the unchanged executable Judge, an untrained 7B
baseline, and aggregate mean/variance reporting before the sealed evaluation.
