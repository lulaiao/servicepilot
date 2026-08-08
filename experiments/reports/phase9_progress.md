# Phase 9 progress: training readiness audit

Date: 2026-08-08  
Status: Phase 9B protocol and 7B dry-run complete; formal SFT not started

## Outcome

Resources are sufficient for a bounded single-GPU LoRA smoke test, but the data
and reward evidence is insufficient for a reportable SFT or GRPO experiment.
No model weights were changed during this audit.

| Gate | Result | Reason |
| --- | --- | --- |
| CUDA allocation | Pass | RTX A6000 GPU 4, PyTorch 2.5.1+cu121 |
| BF16 | Pass | Runtime capability check passed |
| Disk | Pass | 3,402.98 GiB free |
| LoRA smoke | Allowed | Resource gates pass |
| LoRA SFT | Blocked | 24/6/6 SFT records vs 500/100/100 project gate |
| Outcome GRPO | Blocked | 33 train preferences and no reward audits |
| Process GRPO | Blocked | 33 train preferences and no process-reward audits |

## Candidate decision

- Rule Agent: retained authoritative evaluation baseline.
- Qwen2.5-0.5B-Instruct: smoke-test candidate only; prior mode collapse prevents
  using it as a quality candidate.
- Qwen2.5-Coder-1.5B-Instruct: rejected for the role by prior quality evidence.
- Qwen2.5-7B-Instruct: provisional LoRA candidate after the data gate; its prior
  0.8889 task success must beat the 1.0 rule baseline under the same Judge.

## Framework decision

Direct Transformers plus PEFT is the provisional minimal LoRA path. TRL is a
candidate for SFT and GRPO loops. QLoRA/bitsandbytes, DeepSpeed, and
FlashAttention remain deferred because no measured requirement currently
justifies their installation or complexity.

## Next gate

The safe next action is a non-claimable LoRA smoke test that verifies dataset
loading, label masking, adapter targets, forward/backward pass, checkpoint
resume, and peak VRAM on one GPU. In parallel, the executable trajectory catalog
must grow past the declared data gates before formal SFT. GRPO remains prohibited
until deterministic reward tests and offline reward-distribution/hacking audits
exist.

## LoRA smoke result

The bounded Qwen2.5-0.5B BF16 run completed one optimizer step on one train
record. Assistant-only masking retained 83 of 512 tokens. Loss was finite at
1.094936, peak allocated VRAM was 2,692.32 MiB, and the saved Adapter and
optimizer states both reloaded successfully. This validates plumbing only; the
0.5B model remains rejected as a quality candidate and no evaluation metric was
claimed.

The data-remediation design is frozen in `docs/phase9_data_expansion_plan.md`.
Its target is 600/120/120 executable records across at least 200/40/40 semantic
families, with independently authored sealed families and no duplicate-based
count inflation.

## Scenario-family expansion progress

Forty independently reserved sealed families were frozen before train/dev
generation. Their canonical runs reach 40/40 task success with zero
false-success and policy violations. The first constrained train/dev batch adds
60 unique families (49 train, 11 dev), also with 100% authoritative success and
zero semantic-signature overlap with sealed.

Three post-split utterance variants per family now produce 300/300 successful
runs: 147 train, 33 development, and 120 sealed. The canonical export passes
privacy, exact leakage, family leakage, and cross-split near-duplicate gates.
It derives 300 SFT and 471 preference records, of which 204 preferences are
train split.

This is progress toward the diversity gate, not completion. Sealed reaches its
120-record/40-family target, but train/dev have only 49/11 families versus the
200/40 target. Formal SFT and GRPO remain blocked; adding more paraphrases to
existing families cannot satisfy the semantic diversity gate.

## Expanded data gate passed

The second constrained batch raises the accepted dataset to 314 semantic
families and 942 executable records:

| Split | Families | SFT records | Preference records |
| --- | ---: | ---: | ---: |
| Train | 232 | 696 | 1,011 |
| Development | 42 | 126 | 225 |
| Sealed test | 40 | 120 | 207 |

All 942 variants pass the Judge. Privacy violations, exact duplicates,
cross-split family/content overlap, and cross-split near duplicates are zero.
The first v2 split produced 86 near-duplicate pairs; the 0.9 threshold was kept,
and generated order-query/out-of-scope template superfamilies were moved as
units rather than individually hashed across train/dev.

The readiness re-audit now allows LoRA SFT. Outcome and process GRPO remain
blocked solely by missing reward unit, distribution, and reward-hacking audits.
No formal 7B training has started.

## Phase 9B frozen protocol and 7B feasibility

The formal experiment inputs are now frozen in
`experiments/configs/phase9_qwen25_7b_lora_sft_v1.json`: exact model revision,
SFT data hash, four seeds, BF16 LoRA configuration, training limits, checkpoint
rules, dev selection order, termination conditions, and a sealed-test-once
policy. Protocol validation rejects fewer than four unique seeds, selection on
sealed data, inconsistent split counts, and unsafe checkpoint ordering.

An offline Qwen2.5-7B-Instruct dry-run on GPU 4 completed one optimizer step
over 734 input tokens, including 102 assistant-labelled tokens. Loss was finite
at 3.719796; the step took 1.4888 seconds; peak allocated/reserved VRAM was
20,892.78/21,594 MiB. Both the adapter and optimizer state reloaded, with
5,046,272 trainable parameters restored.

This removes the 7B memory and resume uncertainty without making a quality
claim. Formal SFT has not run, and the sealed split has not been inspected for
model selection. The next gate is the predeclared four-seed experiment against
the untrained 7B and rule-Agent baselines under the same executable Judge.

## Phase 9C runner readiness

The per-seed runner now supports frozen-seed validation, data hash and split
checks, assistant-only multi-turn masking, gradient accumulation, periodic
dev-loss evaluation, resumable PEFT/optimizer checkpoints, and resource
reporting. Checkpoint selection is a separate fail-closed step: every candidate
must have executable dev evidence, safety is evaluated first, and sealed reports
are rejected for selection.

A one-step 7B control run processed a full 16-example accumulated batch in
6.8178 seconds of Trainer runtime. Peak allocated/reserved VRAM was
22,346.19/23,318 MiB, and Trainer loaded zero sealed records. This is runner
validation only. The four formal seeds remain unexecuted; the existing Phase 3
scenario catalog is treated as development evidence, and a new frozen
executable sealed catalog is required before final model claims.

## Four-seed SFT training complete

All four frozen seeds completed 129 optimizer steps and produced checkpoints at
steps 25, 50, 75, 100, and 125. Every run used the same model revision and data
hash, loaded zero sealed records, and ended in `awaiting_harness_eval` rather
than selecting by loss.

Across seeds, mean train loss was 0.328702 (sample standard deviation 0.006730).
Checkpoint-125 dev loss averaged 0.000403 (standard deviation 0.000042). Mean
Trainer runtime was 832.41 seconds per seed (standard deviation 4.91), and mean
peak allocated VRAM was 22,372.14 MiB (standard deviation 23.29). The very low
dev loss may reflect an easy/template-aligned dataset and is not evidence of
Agent improvement.

Formal training is complete, but checkpoint selection and quality evaluation
are not. Each of the 20 candidates must next run through the executable dev
Harness. The selector will reject missing evidence and any candidate with a
non-zero high-risk error rate before comparing task success or dev loss.

## Executable dev Harness rejected all checkpoints

All 20 candidates completed the same 36-scenario executable development suite.
No candidate passed the frozen zero-high-risk-error gate, so no checkpoint was
selected and no sealed evaluation was run. Across candidates, task success
averaged 0.80419 (range 0.75–0.8611), high-risk error averaged 0.2111 (range
0.0556–0.2778), False-success averaged 0.079145, and Schema validity averaged
0.919475. Mean scenario latency was 2.39121 seconds and peak inference VRAM was
14,626.2 MiB.

Six learned invalid actions caused runtime exceptions, including selecting a
reschedule operation when no reschedule slot existed. The evaluator now records
these as unsafe failed trajectories and continues the suite. The rule baseline
remained at 1.0 task success with zero high-risk errors and False-success.

Phase 9 SFT v1 is therefore a documented negative result: loss convergence did
not produce a safe executable Agent. A new protocol version and targeted data
remediation are required; sealed evaluation and GRPO remain prohibited.
