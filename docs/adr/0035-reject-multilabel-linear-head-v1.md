# ADR 0035: Reject multi-label linear head v1 after sealed evaluation

- Status: Accepted
- Date: 2026-08-12

## Context

The four-seed three-label linear head achieved perfect results on its synthetic family-split development
set. ADR 0034 therefore froze a new 80-case, manually authored holdout before any inference. The
catalog, protocol, fixed threshold, four head hashes, and one-shot output contract were verified at
runtime.

## Result

No seed passed. Mean macro-F1 was 0.7232 and mean exact-set accuracy was 0.5469, both well below the
frozen 0.85 and 0.80 gates. Complaint escalation recall was 0.3667 for every seed, while its false
positive rate was 0.06, also failing both safety gates. Partial-refund recall ranged from 0.6333 to
0.6667. Delivery recall remained 1.0 but precision fell to 0.7792 because every seed produced 17 false
positives among 20 delivery-negative cases.

Failures concentrated in refund-only (10/10 for every seed), complaint-only (7/10), explicit pairs
(6/10), and three-intent requests (8/10). Results were nearly identical across seeds, so optimizer seed
instability is not a plausible primary explanation.

## Decision

Reject multi-label linear head v1 and forbid Agent integration. The sealed holdout is consumed and may
not be rerun, used for threshold selection, converted into training data, or used to choose another v1
checkpoint.

## Diagnosis

The most likely failure is a data and representation problem rather than insufficient seed count:

- delivery delay appears in 210/240 development-dataset records, encouraging a near-default delivery
  prediction and producing 17/20 false positives out of domain for that label;
- complaint examples use a narrow escalation-action vocabulary, while the independent set uses more
  varied formulations, exposing lexical shortcut learning;
- partial refund has only 30/240 positives and fails especially when it is the sole requested action;
- mean-pooled last-hidden-state features plus a single linear layer do not reliably preserve negation,
  request scope, or independent intent composition under this distribution shift.

These are evidence-backed hypotheses, not a claim that one isolated factor has been causally proven.

## Consequences

The next experiment must change only train-side data and the predeclared representation protocol. It
should rebalance labels, add paraphrase families without copying sealed text, include each label alone
and in all relevant combinations, and introduce train-only contrastive pairs for negated, conditional,
historical, and explicit action scope. Evaluation requires a newly authored holdout version; v1 remains
available only as immutable failure evidence.
