# ADR 0028: Composition adversarial safety gate

- Status: Accepted
- Date: 2026-08-11

## Context

ADR 0027 integrated an evidence-gated delivery-delay plus complaint-escalation binder based on a
small reused-dev diagnostic. Before creating any new holdout, the binder needed broader deterministic
coverage of false-positive conditions, especially those that could trigger an unwanted tool call.

## Decision

Adopt a 120-case iterable train/dev safety contract with these categories:

- 32 explicit delivery plus escalation pairs;
- 24 negated escalation requests;
- 24 conditional future requests;
- 16 historical requests;
- 8 delivery-only and 4 escalation-only cases;
- 8 three-intent cases containing a separate refund action;
- 4 cases where the model output is unrelated to otherwise compositional text.

The acceptance gate requires zero false bindings. The binder must abstain for conditional,
historical, negated, unrelated-model, and existing-third-intent inputs. Conservative missed bindings
are preferable to an unwanted secondary action, although the final gate also reports them.

## Evidence

The initial binder passed 86/120 cases, with eight false bindings and 26 missed bindings. After adding
explicit abstention for conditional, historical, and third-intent conditions, it passed 112/120 with
zero false bindings. Adding two general delivery status forms (`延误` and `没有完成`) produced
120/120, with zero false and zero missed bindings.

All iterations are recorded. This is an intentionally editable train/dev contract, not sealed
evidence, and no model inference was performed.

## Consequences

- Future changes to composition binding must pass all 120 cases and the full regression suite.
- The safety argument distinguishes false binding from missed binding instead of reporting only
  aggregate accuracy.
- Generalization remains unproven; a separately authored holdout is still required before a final
  acceptance claim.
