# ADR 0017: Pass reward audit but block objective-mismatched GRPO

- Status: Accepted
- Date: 2026-08-09

## Context

Formal classifier SFT v3 passed repeated dev and sealed executable evaluation.
The expanded dataset also contains 1,011 train preference pairs, satisfying the
project's numeric GRPO data gate. Numeric scale alone does not establish that a
reward is safe or that its optimization target matches the deployed component.

## Evidence

Outcome and process rewards now apply non-additive negative hard gates for
unsafe high-risk execution, False-success, and invalid structured output. The
tool-decision reward does not inspect persuasive completion text and requires
confirmation, idempotency, and the domain-specific optimistic-lock field for
high-risk writes.

The offline audit covered all 1,011 train preference pairs. Chosen reward was
1.5, rejected reward averaged -1.37982, minimum group margin was 2.5, and no
group had zero or reversed margin. All three initial reward-hacking probes
passed. A fail-closed first run exposed three coupon restoration examples whose
valid version field is `expected_order_version`; correcting the reward contract,
not the data, removed those false unsafe classifications.

TRL 0.14.0 exposes the required `GRPOTrainer` and `GRPOConfig`, and GPU 2 was
idle during the audit. However, the formal SFT model is deployed as an
intent/slot classifier while the preference records supervise tool decisions.
Training that classifier adapter on tool-action completions would repeat the
objective/deployment mismatch documented in the rejected SFT v1 experiment.

## Decision

Record the reward unit, distribution, and hacking audits as passed. Add a
separate `grpo_deployment_contract_validated` readiness gate and leave it false.
Do not run GRPO merely because a GPU is available.

Before a smoke run, choose and freeze one coherent contract: either generate
on-policy intent/slot completions and evaluate them through the executable
Harness, or introduce and baseline a separately deployed learned tool policy.
The former is preferred because it preserves the current architecture and
requires less new authority.

## Consequences

Phase 9 gains an auditable reward subsystem without making an unsupported RL
claim. Outcome-only GRPO remains the next candidate after an on-policy Harness
adapter is implemented. Process-reward GRPO remains deferred until process
signals can be attributed to the same learned component.
