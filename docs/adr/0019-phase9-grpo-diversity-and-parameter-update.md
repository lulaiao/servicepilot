# ADR 0019: Admit a bounded GRPO experiment after diversity and update checks

- Status: Accepted
- Date: 2026-08-09

## Context

The first outcome GRPO smoke had zero within-group reward variance. A frozen
inference-only diagnostic therefore compared temperatures 0.9, 1.1, and 1.3 on
six hard development prompts, with four generations per prompt. No parameters
were updated and no sealed records were loaded.

## Evidence

At temperature 0.9, Schema validity was 1.0, two of six groups had valid reward
variance, and unsafe hard-gate rate was zero. Temperatures 1.1 and 1.3 also
produced variance, but 1.3 reduced Schema validity to 0.9583. The lowest setting
that passed all gates, 0.9, was selected rather than maximizing diversity.

Smoke v2 used two identified hard prompts and produced reward standard deviation
1.9445 with a non-zero gradient. Inspection showed its one-step linear schedule
reported learning rate zero, so it did not prove a parameter update. This was
treated as a failed validation even though its original four gates passed.

Smoke v3 froze the same prompts and sampling but used a constant `1e-6` learning
rate and added explicit learning-rate, gradient, and parameter-delta gates. It
completed one step with reward standard deviation 1.9445, gradient norm 0.5830,
LoRA parameter delta L2 0.002235, and KL approximately 0.00007585. Peak allocated
VRAM was 34,798.67 MiB and no sealed data was loaded.

## Decision

Accept smoke v3 as validation of generation, executable reward, backward, and
optimizer-update mechanics. This is not evidence that GRPO improves the Agent.

A bounded multi-step dev-only experiment may now be designed. It must freeze
step count, seeds, prompt sampling, KL limit, safety termination conditions, and
pre/post executable evaluation before running. Process-reward GRPO remains
blocked, and sealed evaluation remains prohibited until a dev checkpoint is
selected without post-hoc tuning.
