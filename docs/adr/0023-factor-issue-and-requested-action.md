# ADR 0023: Factor issue type from requested action

- Status: Accepted for bounded diagnostic implementation
- Date: 2026-08-10

## Context

The deployed classifier uses one `primary_intent` field for two different concepts:

1. the business incident the user reports, such as a wrong item or duplicate charge;
2. the operation the user requests, such as cancellation, refund, or rescheduling.

This makes labels mutually ambiguous. For example, “return the duplicated 58 yuan charge” is both a
`duplicate_charge` incident and a refund request. The v4 gold contract chooses the incident while the
model repeatedly chooses the requested operation.

The ambiguity survived four controlled interventions:

- v5 train-only cancel/reschedule and multi-intent hard negatives;
- a longer 20-step v5 training horizon;
- v6 train-only incident-versus-remediation contrasts;
- an explicit Prompt Contract v2 tested with both the best v5 adapter and the unadapted base model.

Lower token loss did not improve the three stable semantic errors. Prompt v2 changed no prediction
with the adapter and the base model retained the same errors. More examples, steps, or prompt text are
therefore not justified on the current abstraction.

## Decision

Introduce a factored classifier contract:

- `issue_type`: the observed business condition, or `none` when the request is action-only;
- `requested_actions`: a set of independently requested operations;
- `slots`: typed evidence visible in the utterance;
- safety and confidence fields retained from the existing contract.

Examples:

| Utterance semantics | issue_type | requested_actions |
|---|---|---|
| End the order without refund | none | cancel_order |
| Wrong item and return 12 yuan | missing_or_wrong_item | partial_refund |
| Duplicate charge and return 58 yuan | duplicate_charge | partial_refund |
| Delivery delay and human complaint | delivery_delay | complaint_escalation |

A deterministic projection converts the factored result into legacy routing intents during migration.
The projection must never infer an action that the user did not request.

## Consequences

- Multi-intent output becomes compositional instead of overloading primary/secondary precedence.
- Incident metrics and action metrics can be reported separately.
- Existing Agent routing can migrate incrementally through a deterministic compatibility layer.
- Existing v4 dev results remain historical evidence but cannot serve as the only acceptance set for the
  new Schema. A new independently authored dev set and later a sealed set are required.
- No further SFT or GRPO is authorized until deterministic Schema, projection, and leakage tests pass.

## Rejected alternatives

- More v6 steps: prior longer training reduced loss without changing semantic errors.
- More paraphrases under the same labels: v5 and v6 already tested this and increased tuning pressure on
  the reused dev set.
- Longer prompt rules: doubled latency with no quality gain.
- Guardrail override: would conceal classifier errors and previously demonstrated harmful interventions.
