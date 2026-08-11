# ADR 0032: Multi-label composition dataset v1

- Status: Accepted as a bounded training pilot
- Date: 2026-08-11

## Context

Rule binding, lexical centroids, and frozen-embedding centroids all failed independent safety or
quality gates. Training a supervised BCE head against six dev examples would overfit, so a larger
independently partitioned dataset is required before another model experiment.

## Decision

Create a 240-record composition pilot with three independent labels:

- `delivery_delay`;
- `complaint_escalation`;
- `partial_refund`.

The data contains 80 semantic families with three surface variants each. Splitting occurs at family
level: 64 families/192 records for train and 16 families/48 records for dev. Categories cover explicit
pairs, three-intent requests, delivery-only, negated escalation, conditional future escalation,
historical escalation, escalation-only, and unrelated inputs.

No sealed records are included. The freeze gate rejects exact text overlap, semantic-signature overlap,
and cross-split character 5-gram similarity at or above 0.8.

## Rationale

- Family splitting prevents variants of one semantic recipe from appearing in both train and dev.
- Independent binary labels allow a BCE head to preserve a third intent instead of replacing the
  generated secondary array.
- The pilot is large enough to test a small head, but remains synthetic and cannot support a production
  claim by itself.

## Consequences

- A supervised-head protocol may now be specified without using any consumed holdout.
- Metrics must report per-label precision/recall/F1, exact-set accuracy, especially false-positive
  escalation rate, and resource cost.
- A winner still requires an independently authored holdout and executable Agent evaluation.
