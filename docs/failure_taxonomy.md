# Failure taxonomy

## Phase 2 typed tool failures

| Code | Retryable | Recovery |
| --- | --- | --- |
| `VALIDATION` | No | Repair arguments before another call |
| `NOT_FOUND` | No | Reconfirm identifier or list recent records |
| `TIMEOUT` | Yes, bounded | Exponential backoff; stop after configured attempts |
| `TRANSIENT` | Yes, bounded | Retry within tool and retry budgets |
| `EMPTY_RESULT` | No automatically | Broaden lookup, clarify, or escalate |
| `PARTIAL_RESULT` | No automatically | Re-query a narrower authoritative tool |
| `CONFIRMATION_REQUIRED` | No | Preview, explain impact, obtain confirmation |
| `VERSION_CONFLICT` | No | Re-read state and create a new preview |
| `IDEMPOTENCY_CONFLICT` | No | Treat key reuse as a caller defect/security event |
| `POLICY_VIOLATION` | No | Explain policy evidence or escalate |
| `BUDGET_EXCEEDED` | No | Stop the loop and ask/hand off |
| `UNKNOWN_TOOL` | No | Re-plan using discovered tools |
| `INTERNAL` | No | Fail closed and escalate |

## Deterministic fault hooks

`FaultPlan` can reproduce timeout, transient transport failure, empty result,
partial result, and response loss after a committed write. Version conflict and
invalid schema are reproduced using authoritative state and Pydantic contracts.

The response-loss test commits a refund, raises a retryable synthetic transport
error, retries with the same idempotency key, and asserts that exactly one
refund exists. Retrying validation, policy or version failures is deliberately
forbidden.

Actual remote transport timeout behavior will be covered when Streamable HTTP is
introduced. Phase 2's domain calls are in-process and non-blocking; injected
timeouts test recovery policy rather than operating-system cancellation.

Memory conflict, retrieval conflict, and Monitor false-positive/negative
families remain deferred to their owning phases.
