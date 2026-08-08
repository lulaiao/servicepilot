# ADR 0008: Keep the Phase 7 Monitor least-privilege and advisory

- Status: Accepted
- Date: 2026-08-08

## Context

The Phase 7 Monitor must identify execution and safety failures without becoming
a second Agent, a hidden business-write path, or an unbounded source of model
calls. It also needs synchronous and asynchronous operation while preserving the
same deterministic decisions.

## Decision

Use a typed, deterministic Monitor over three redacted scopes only: trace
summary, Judge result, and Harness budgets. It receives no Repository, raw tool
arguments, credentials, or write-capable dispatcher. Its output is limited to
findings and `alert`, `block`, or `handoff` recommendations; enforcement remains
with the existing Harness and Guardrail boundaries.

The first rule set covers thirteen fault classes: false-success, policy
violation, forbidden action, missing evidence, budget exhaustion, retry storm,
tool failure, duplicate write, unsafe lost-response recovery, version conflict,
Prompt Injection, unresolved memory conflict, and unconfirmed high-risk write.
The asynchronous implementation uses a bounded queue and applies backpressure;
it delegates evaluation to the same deterministic rule engine as synchronous
execution.

## Evidence

The frozen 26-case calibration contains one isolated positive for each fault
class and thirteen clean controls. Revision `657d314` reaches precision 1.0,
recall 1.0, and harmful-intervention rate 0.0. A real clean Harness trajectory
also passes through the read-only adapter without a finding.

These are implementation-calibration results, not evidence of production
generalization. Phase 7 acceptance still requires at least 1,000 executable
trajectories, mixed and correlated failures, recovery assertions, and measured
sync/async overhead.

## Rejected alternatives

- Giving the Monitor Repository or Dispatcher access is rejected because it
  violates least privilege and can silently duplicate business actions.
- Using an LLM Monitor at this gate is rejected because the current fault
  classes have authoritative structured signals and do not justify added
  latency, nondeterminism, or a second model-safety surface.
- Treating recommendations as direct enforcement is rejected because it blurs
  ownership between observation and execution controls.

