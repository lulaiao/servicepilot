# ADR 0018: Stop outcome GRPO smoke on zero group variance

- Status: Accepted
- Date: 2026-08-09

## Context

ADR 0017 blocked GRPO because tool-decision preferences did not match the
deployed intent/slot classifier. An on-policy adapter now sends sampled
classifier JSON through `RoutedRuleAgent`, real deterministic tools, and the
deterministic Judge. Four inputs always owned by multi-intent or injection
Guardrails are excluded from the model training view.

The contract audit used 32 model-owned scenarios and 96 executions covering
gold, invalid-Schema, and valid confusable completions. All gold completions
succeeded, minimum confusable reward margin was 2.25, and no margin was zero or
negative. Wrong predictions rescued by a Guardrail receive explicit negative
credit rather than inheriting the successful downstream outcome.

## Smoke evidence

The frozen smoke used Qwen2.5-7B-Instruct revision
`a09a35458c702b33eeacc393d103063234e8bc28` with the selected classifier SFT v3
adapter, BF16, two prompts, two generations per prompt, and one optimizer step.
It loaded zero sealed records and completed without OOM in 5.3032 seconds. Peak
allocated VRAM was 34,624.78 MiB.

Both generations for each prompt were byte-identical and correct. All four
rewards were 1.75, group reward standard deviation was zero, and the reported
loss was effectively zero. The executable reward pipeline works, but GRPO had
no advantage signal and therefore performed no meaningful learning.

## Decision

Mark the smoke as failed by its predeclared non-zero group-variance gate. Do not
describe it as successful RL training and do not extend steps or seeds.

Before retrying, run an inference-only diversity diagnostic over frozen hard
development prompts and a small predeclared grid of temperature and generation
count. A retry is allowed only if the diagnostic produces valid, safety-bounded
reward variance without relying mainly on malformed JSON. Process-reward GRPO
remains blocked by its separate deployment contract.
