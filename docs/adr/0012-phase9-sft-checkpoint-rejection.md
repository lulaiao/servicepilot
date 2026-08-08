# ADR 0012: Reject all Phase 9 SFT checkpoints at the safety gate

- Status: Accepted
- Date: 2026-08-08

## Context

Four frozen LoRA runs produced 20 checkpoints. The protocol requires every
candidate to pass the same executable development Harness and requires zero
high-risk errors before task success or dev loss can influence selection.

## Evidence

All 20 candidates completed 36 development scenarios. Mean executable task
success was 0.80419, mean high-risk error rate was 0.2111, and mean
False-success was 0.079145. The best observed task success was 0.8611, but its
high-risk error rate was 0.1667. The lowest observed high-risk error rate was
0.0556, still above the frozen zero threshold. Six invalid learned actions
raised runtime errors; the evaluator records these as unsafe failed trajectories
instead of aborting the suite.

The deterministic rule baseline remained at 1.0 task success, zero high-risk
errors, and zero False-success under the same Harness.

## Decision

Reject all 20 checkpoints. Do not run the sealed executable evaluation, because
there is no eligible checkpoint and sealed data cannot be used to rescue or
select a model. Do not claim that SFT improved Agent quality merely because dev
loss converged.

## Consequences

The experiment is still useful negative evidence: the current SFT objective
teaches trajectory-token imitation but does not reliably preserve transactional
safety or action preconditions. The next training iteration must be a new,
versioned protocol. It should add explicit invalid-action and slot-precondition
examples, rebalance high-risk/False-success failures, and establish a dev safety
improvement before any sealed test. GRPO remains blocked by its separate reward
audits and must not be used as an ad-hoc repair.
