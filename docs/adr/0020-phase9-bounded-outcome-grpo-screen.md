# ADR 0020: Freeze a single-seed bounded outcome GRPO screen

- Status: Accepted, execution pending GPU availability
- Date: 2026-08-09

## Context

Smoke v3 validated executable reward generation, backward propagation, and a
real LoRA parameter update. It did not establish that multiple updates improve
the Agent. Repeated seeds would be wasteful before a bounded single-seed screen
demonstrates safety and non-regression.

## Decision

Freeze a 10-step, seed-20260809 development-only screen using six hard prompts,
temperature 0.9, two generations, constant learning rate `5e-7`, and KL
coefficient 0.04. The selected SFT v3 seed-20260808 checkpoint-100 adapter is
the starting point. No sealed records may be loaded.

Training terminates fail-closed before an optimizer update when a sampled batch
falls below 0.75 Schema validity or emits an unsafe/False-success reward hard
gate. Logged KL above 0.05 stops further steps. Completion requires all 10
steps, overall Schema validity at least 0.95, at least three steps with non-zero
reward standard deviation, runtime-error rate at most 0.25, KL within limit,
and a measurable parameter update.

Passing training gates only saves a candidate adapter. That adapter must then
run the same frozen 36-scenario executable dev Harness as its SFT baseline. Any
task-success, False-success, policy, or high-risk safety regression blocks
repeated seeds and sealed evaluation.

## Resource state

The runner and protocol pass CPU validation, but execution is deferred because
GPU 2 became occupied after protocol freeze and all other visible cards were
also active. Resource availability does not change the frozen parameters.
