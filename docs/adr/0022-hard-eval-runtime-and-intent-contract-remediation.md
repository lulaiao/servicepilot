# ADR 0022: Remediate runtime and multi-intent contract failures before more training

## Status

Accepted.

## Context

The one-shot Hard Eval v2 reduced SFT v3 executable success from 94.44% to 82.92%.
It exposed ten Agent runtime errors and showed that intervention counts alone could not
distinguish helpful Guardrails from harmful ones.

Nine runtime errors came from a user-simulator FSM that rejected a second, separately
previewed confirmation. One came from dispatching a reschedule action when no new time
could be supplied. The audit also found a contract contradiction: the structured-output
prompt excludes `multi_intent` as a primary executable intent, while the training target
previously emitted it. The deployed Agent instead requires `delivery_delay` as primary
and `complaint_escalation` as secondary.

## Decision

- Allow repeated confirmations only when every write has its own preview and
  confirmation request.
- Treat unavailable refund or reschedule slots as an auditable safe failure instead of
  propagating a runtime exception.
- Encode multi-intent training targets using the executable primary-plus-secondary
  contract.
- Report Guardrail rescue, harm, and neutral counts by comparing raw, selected, and
  expected executable intent tuples.
- Keep Hard Eval v2 diagnosis-only. These changes are validated on unit and development
  data; Hard Eval v2 is not reused for model or threshold selection.

## Consequences

The existing SFT v3 checkpoint and its dataset remain immutable historical evidence.
The corrected target changes training labels, so any future model must use a new dataset
and protocol version. A new independent Hard Eval must be frozen only after remediation
choices and development gates are fixed.
