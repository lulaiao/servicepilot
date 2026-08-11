# ADR 0027: Evidence-gated compositional intents

- Status: Accepted for diagnostic integration
- Date: 2026-08-11

## Context

Classifier v7 retained the correct `delivery_delay` primary intent but omitted the independent
`complaint_escalation` secondary intent in one reused-dev case. The previous Harness already used
rule evidence to require both actions before claiming completion, so it prevented false success but
could not execute the missing second action.

Adding more paraphrases is not justified after v5-v7 demonstrated interference between single-intent
remediation and multi-intent completeness. A full factored rule-first classifier also failed its
independent holdout. The narrower requirement is to compose two independently explicit actions,
without replacing general model classification.

## Decision

Introduce an evidence-gated composition binder at the Agent boundary:

- require positive textual evidence for both a delivery incident and escalation request;
- reject negated escalation language;
- only intervene when the model already selected delivery delay or complaint escalation;
- normalize the executable tuple to delivery delay plus complaint escalation;
- expose `composition_binding_count` and intervention rescue/harm records in the Harness report.

The binder does not infer refund, cancellation, coupon, or scheduling actions and does not operate on
unrelated model outputs.

## Evidence

CPU replay over saved v7 checkpoint-10 dev predictions changed one of 36 tuples, rescued the only
multi-intent omission, and harmed zero previously correct tuples. Executable Harness replay using the
same recorded predictions improved task success from 35/36 to 36/36 with one binding, zero policy
violations, and zero false success. V5 replay changed zero tuples.

All evidence uses the reused development catalog. No model inference or sealed evaluation was run,
so the result is a bounded diagnostic and not a generalization claim.

## Consequences

- The Harness can now convert explicit compositional evidence into execution instead of using it only
  to suppress false completion.
- The intervention is independently observable and ablatable.
- V7 remains rejected as a model candidate under ADR 0026; this change does not retroactively select
  it.
- A broader train/dev adversarial set and a new independently authored holdout are required before
  production acceptance.
