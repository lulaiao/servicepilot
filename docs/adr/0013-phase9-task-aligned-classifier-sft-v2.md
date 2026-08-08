# ADR 0013: Align SFT v2 with the deployed classifier contract

- Status: Accepted for data remediation; training protocol not yet frozen
- Date: 2026-08-08

## Context

SFT v1 optimized full multi-turn Agent trajectory text, while the learned model
used by the executable Harness only receives `build_intent_prompt(text)` and
must return one `IntentResult` JSON object. The resulting loss convergence was
therefore not evidence for the deployed task. All 20 v1 checkpoints failed the
high-risk gate.

## Decision

Create a new classifier-specific SFT view whose user message is the exact
deployment prompt and whose assistant message validates against the exact
deployment output schema. Slot labels are extracted only from literal user text;
hidden scenario order IDs, amounts, and state are never copied into targets.

Preserve the existing family splits. Add 60 train-only remediation records for
the aggregate failure classes missing-vs-refund, partial-vs-full,
complaint-vs-delivery, coupon-vs-reschedule, and injection-stop. These records
are derived from train families; no development failure utterance or sealed
instance is copied into train.

## Consequences

The resulting view contains 756 train, 126 dev, and 120 sealed records, with
zero cross-split family overlap. This dataset is eligible for audit, but it does
not authorize training yet. SFT v2 needs a new frozen protocol and a cheap
task-aligned smoke/ablation showing that the corrected objective improves
classifier Schema and safety metrics before another four-seed 7B run.
