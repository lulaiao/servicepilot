# ADR 0036: Balance multi-label v2 and isolate representation choice

- Status: Accepted as a train-only development protocol
- Date: 2026-08-12

## Context

The v1 head failed sealed evaluation with negligible seed variance. Evidence implicated label imbalance,
narrow lexical templates, and a representation that did not preserve request scope. The consumed v1
holdout is excluded from all v2 records and remains unavailable for tuning.

## Decision

Freeze a 640-record synthetic v2 development dataset containing 320 semantic families and two surface
variants per family. Each of the eight possible label sets has 80 records, so delivery delay, complaint
escalation, and partial refund each have exactly 50% prevalence. The 512/128 train/dev split occurs by
family; exact and semantic-signature overlap are zero, and maximum character 5-gram similarity is
0.7733 under the unchanged 0.8 near-duplicate gate.

Every request contains independent positive or contrastive clauses for all three labels. Contrastive
clauses cover explicit negation, past action, future conditions, and policy-only questions without
copying v1 sealed text.

Compare exactly two representations while holding the model, Adapter, linear head, optimizer, four
seeds, 0.5 threshold, and gates fixed:

1. raw user text with attention-masked mean pooling;
2. an explicit label-definition instruction with last non-padding token pooling.

Selection first requires all four seeds to pass every gate, then uses mean exact-set accuracy, mean
macro-F1, complaint false-positive rate, and embedding latency in that order.

## Consequences

This experiment can determine whether task-conditioned representation improves balanced synthetic dev
performance. It cannot rehabilitate v1 sealed results or authorize Agent integration. If a candidate
passes, a new independently authored v2 holdout must be frozen before any external-quality claim.
