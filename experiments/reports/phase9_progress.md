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

## SFT v2 task-aligned data remediation

Root-cause review found an objective/deployment mismatch: v1 trained full Agent
trajectory text, but the deployed learned component is a single-turn structured
intent/slot classifier. The v2 data view now uses the exact deployment Prompt
and `IntentResult` JSON schema. Labels expose only slots literally present in
the user utterance, preventing hidden scenario-state leakage.

The exported v2 view contains 1,002 records: 942 family-preserving base records
plus 60 train-only failure-remediation examples. Split counts are 756/126/120,
cross-split family overlap is zero, and no dev failure instance or sealed record
was copied into train. Training remains paused until a new protocol is frozen.

## SFT v2 bounded screening stopped

The frozen 25-step classifier screening completed with dev loss 0.09953,
82.77-second Trainer runtime, 16,426.9 MiB peak training VRAM, and zero sealed
records loaded. Executable dev Schema validity improved to 1.0 and runtime
errors fell to zero. High-risk error fell to 0.0556 versus the v1 candidate mean
of 0.2111.

The screening nevertheless failed its utility gate: task success was 0.8056,
below the untrained 7B baseline of 0.8889, while False-success rose to 0.1667.
All three multi-intent scenarios failed. Four-seed v2 training and sealed
evaluation are therefore not authorized. The next remediation must target
multi-intent execution and honest non-completion before another GPU run.

## SFT v3 completion-guard ablation

A narrow deterministic guard now overrides the learned classifier only for
explicit multi-intent conjunctions and Prompt Injection. With the same v2
checkpoint, multi-intent success improved from 0/3 to 3/3, overall task success
from 0.8056 to 0.8889, and False-success from 0.1667 to 0.0833. Four of 36
classifications were overridden. High-risk error remained 0.0556, so formal
training and sealed evaluation remain blocked.

An independent Output Completion Verifier now requires successful tool evidence
for every deterministic required intent before allowing a completion claim. On
the same checkpoint and scenarios it preserved 0.8889 task success and 3/3
multi-intent success while reducing False-success from 0.0833 to zero. The four
real failures remain visible. High-risk error is still 0.0556, so the next gate
is pre-dispatch intent/action alignment rather than more training.

The high-risk intent/action alignment guard now fail-safe reroutes only when
deterministic high-risk evidence disagrees with the learned model. Two such
overrides reduced unsafe high-risk error from 0.0556 to zero, raised task success
from 0.8889 to 0.9167, and preserved zero False-success. The combined v3 Harness
therefore passes the dev safety/utility gate; a new repeated protocol may be
frozen, but the screening checkpoint is still not eligible for sealed testing.

## Formal classifier SFT v3 complete

Four frozen seeds each completed 141 optimizer steps over the same 756-record
training split and produced checkpoints at steps 25, 50, 75, 100, and 125. The
trainer loaded zero sealed records. Mean training runtime was 452.71 seconds and
peak allocated training VRAM was approximately 16,428 MiB.

All 20 checkpoints then ran the same 36-scenario executable dev Harness. The
safety-first selector chose steps 100, 75, 125, and 75 for seeds 20260808 through
20260811. This variation is direct evidence that minimum dev loss is not a
sufficient Agent checkpoint criterion. One non-selected checkpoint had a 0.0556
high-risk error rate and was excluded by the safety gate.

Across the four selected checkpoints, executable dev task success and final-state
accuracy were both 0.9444 with zero cross-seed standard deviation. Policy
violation, False-success, and unsafe high-risk error were all zero; Schema
validity was 1.0. Mean scenario latency was 1.9008 seconds, mean P95 was 2.1423
seconds, and peak inference VRAM was 14,626.2 MiB.

After selection and without further tuning, each selected checkpoint was run
exactly once on `sealed_test`. Sealed task success and final-state accuracy were
again 0.9444 for all four seeds, with zero policy violation, False-success, and
unsafe high-risk error. Mean scenario latency was 1.9743 seconds and mean P95 was
2.3140 seconds. Raw artifact locations, report hashes, revisions, and aggregate
metrics are recorded in
`experiments/manifests/phase9_classifier_sft_v3_formal.json`.

This completes the formal SFT v3 evidence gate. The result supports a bounded
claim about the frozen 36-scenario Harness; it is not evidence of production
generalization. The next Phase 9 gate is reward audit and a small GRPO smoke
experiment, not immediate large-scale RL training.

## Reward audit passes; GRPO contract remains blocked

Deterministic outcome, process, and structured tool-decision rewards now enforce
non-additive negative hard gates for unsafe high-risk actions, False-success,
and invalid Schema output. Seven focused unit tests cover safety dominance,
confirmation controls, domain-specific coupon versioning, grounding, and
completion-claim reward hacking.

The distribution audit evaluated all 1,011 train preference pairs. Chosen reward
was 1.5, rejected reward averaged -1.37982, minimum within-group margin was 2.5,
and zero-margin and reversed groups were both zero. All adversarial probes
passed. The first audit intentionally failed on three coupon restores and
revealed that their valid lock field is `expected_order_version`; the reward
contract was corrected and the audit rerun rather than silently dropping data.

GRPO is not yet authorized. The selected v3 adapter is an intent/slot classifier,
whereas the preference dataset targets tool decisions. Optimizing one as if it
were the other would repeat the v1 objective/deployment mismatch. A new explicit
readiness gate now requires an on-policy executable reward adapter for the
deployed classifier before even a smoke run. GPU availability does not override
this correctness gate.

## Outcome GRPO on-policy smoke stopped on zero variance

The new on-policy adapter preserves the deployed classifier Prompt and Schema,
then executes sampled predictions through the routed Agent, tools, and
deterministic Judge. Thirty-two model-owned scenarios passed contract audit;
four Guardrail-owned multi-intent/injection scenarios were excluded. Across 96
gold, invalid, and valid-confusable executions, minimum confusable reward margin
was 2.25 with no zero or reversed groups. Guardrail rescues and classifier
contract mismatches receive explicit negative credit.

The frozen one-step 7B smoke completed without OOM and loaded zero sealed
records. It performed four executable reward evaluations in 5.3032 seconds with
34,624.78 MiB peak allocated VRAM. However, the two samples within each prompt
were byte-identical, all rewards were 1.75, reward standard deviation was zero,
and loss was effectively zero. The smoke therefore failed its predeclared
variance gate and is not evidence of RL improvement.

The next action is an inference-only generation diversity diagnostic on frozen
hard dev prompts. Training retries remain prohibited until useful reward
variance is demonstrated without depending on malformed JSON.

## Diversity diagnostic and GRPO optimizer smoke pass

The frozen inference-only diagnostic evaluated temperatures 0.9, 1.1, and 1.3
over six hard dev prompts and 72 total completions. Temperature 0.9 was the
smallest setting to pass: Schema validity 1.0, two valid non-zero-reward groups,
and zero unsafe hard-gate rate. Temperature 1.3 increased unique completions but
reduced Schema validity to 0.9583, so it was not preferred.

Smoke v2 then produced reward standard deviation 1.9445 and a non-zero gradient,
but forensic inspection found learning rate zero from the one-step linear
scheduler. It validated reward and backward mechanics but not an optimizer
update and was rejected despite its original gates.

Smoke v3 used the same frozen prompts and temperature with a constant `1e-6`
learning rate plus explicit optimizer gates. It recorded gradient norm 0.5830,
LoRA parameter delta L2 0.002235, KL 0.00007585, and 34,798.67 MiB peak allocated
VRAM. All four completions were Schema-valid; rewards included successful
execution, Guardrail rescue, and a safely captured runtime-error trajectory.
All v3 smoke gates passed with zero sealed records loaded.

This validates only the one-step GRPO pipeline. A quality claim still requires
a predeclared multi-step protocol, repeated seeds, pre/post executable dev
comparison, safety termination gates, and later one-time sealed evaluation.

## Bounded outcome GRPO screen frozen

A single-seed 10-step screening protocol is frozen before execution. It uses six
hard dev prompts, temperature 0.9, two generations, constant `5e-7` learning
rate, and zero sealed records. Unsafe/False-success reward gates or batch Schema
validity below 0.75 terminate before an optimizer update; KL above 0.05 stops
subsequent steps.

Completion additionally requires all 10 steps, overall Schema validity at least
0.95, at least three non-zero-reward-variance steps, runtime-error rate no more
than 0.25, KL within limit, and a measurable LoRA parameter update. A passing
adapter must still match or beat the selected SFT baseline on the unchanged
36-scenario executable dev Harness before repeated seeds are authorized.

Execution is currently pending: GPU 2 acquired an unrelated active workload
after the protocol was frozen, and the remaining cards were also active. The
runner, JSON protocol, Ruff, mypy, and full CPU regression are ready; no
parameter will be changed when a GPU becomes available.

## Bounded outcome GRPO screen rejected

The frozen 10-step screen later ran on an idle GPU 0. All training-mechanics
gates passed: 40 executable rewards, no safety termination, Schema validity
0.95, runtime-error rate 0.025, maximum KL 0.0001992, four non-zero-variance
steps, and LoRA parameter delta L2 0.002973. It loaded zero sealed records and
used 34,855.41 MiB peak allocated VRAM.

The unchanged 36-scenario dev Harness showed no utility gain. Task success and
final-state accuracy remained 0.9444, with the same order-query and escalation
failures. Policy violation, False-success, unsafe high-risk error, and runtime
errors stayed at zero, but Schema validity regressed from 1.0 to 0.9722. The new
failure emitted unsupported secondary intent `quality_problem` for a full-refund
request. Mean and P95 latency also increased.

The fail-closed advancement comparison therefore rejected the candidate on
`strict_task_success_gain` and `schema_not_regressed`. Repeated GRPO seeds and
sealed evaluation are prohibited. Formal SFT v3 remains the selected learned
baseline; this GRPO run is retained as a reproducible negative result.
