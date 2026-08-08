# Phase 9 progress: training readiness audit

Date: 2026-08-08  
Status: Phase 9A complete; training not started

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
