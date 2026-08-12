# ADR 0034: Freeze multi-label holdout v1 before inference

- Status: Accepted
- Date: 2026-08-12

## Context

ADR 0033 accepted the three-label linear head only as a synthetic development candidate and required a
new independently authored holdout before Agent integration. The earlier composition holdout has
already been consumed and tests a binary rule binder rather than this head, so it cannot be reused.

## Decision

Freeze 80 manually authored Chinese requests across eight equal categories: explicit delivery plus
complaint, three intents, delivery only, negated complaint, conditional or historical complaint,
complaint only, partial refund only, and delivery plus refund with complaint explicitly excluded.

The catalog contains 60 delivery-delay, 30 complaint-escalation, and 30 partial-refund positives. It has
no normalized exact overlap with the 240-record training/development set; maximum cross-dataset
character 5-gram Jaccard similarity is 0.1034, below the predeclared 0.8 rejection threshold.

Before any inference, retain the candidate's fixed 0.5 threshold and original quality gates. All four
predeclared seed heads must independently achieve macro-F1 at least 0.85, exact-set accuracy at least
0.80, complaint recall at least 0.80, and complaint false-positive rate at most 0.05.

## Execution contract

- The evaluator verifies catalog, protocol, and all four head hashes.
- The shared frozen representation is computed once under the same model revision and Adapter.
- The output path is one-shot: an existing result forbids a rerun.
- No threshold, data, head, or gate change is allowed after seeing results.
- Failure rejects Agent integration; it does not authorize tuning on this holdout.

## Consequences

The holdout is now sealed but unconsumed. Its result remains `TBD` until the one-shot GPU command is
run. Passing this functional gate still does not prove executable Agent benefit; it only authorizes the
next same-budget Agent ablation.
