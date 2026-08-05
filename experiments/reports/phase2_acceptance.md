# Phase 2 acceptance report

Date: 2026-08-05  
Phase 1 commit: `2a98da7`  
Runtime: CPython 3.11.15, project-private `.venv`

## Delivered

- Official MCP Python SDK v2.0.0 selected with primary-source evidence and ADR.
- Editable installation with all declared development dependencies resolves
  successfully and `pip check` reports no broken requirements.
- Five MCP servers and 22 discoverable typed tools.
- Pydantic request validation with forbidden unknown fields and bounded values.
- Transport-independent Service Registry; high-risk writes still require
  TransactionService preview/confirmation/idempotency/version checks.
- Reliable Gateway with trace ID, duration, result summary, tool budget,
  bounded retry, exponential backoff and stable error taxonomy.
- Deterministic timeout, transient, empty, partial and post-commit
  response-loss hooks; state-driven version conflict reproduction.
- In-memory MCP v2 Client discovery and structured-call contract tests.

## Verification

```text
PYTHONPATH=src .venv/bin/python -m pytest -q
42 passed

.venv/bin/python -m ruff check src tests
All checks passed!

PYTHONPATH=src .venv/bin/python -m mypy src
Success: no issues found in 29 source files
```

## Acceptance evidence

- All 22 tools generate MCP schemas and are discoverable from actual SDK clients.
- Every business server completes a representative structured read call.
- Invalid input returns `VALIDATION` without retry.
- Transient failure succeeds on the second bounded attempt.
- Three injected timeouts stop after three total attempts.
- Empty and partial results receive distinct failure codes.
- Lost refund response retries and leaves exactly one refund.
- Version conflict fails closed without automatic retry.
- Missing confirmation was already audited by the underlying Phase 1 service.

## Known limitations and Phase 3 risks

- Contract tests use the SDK's in-memory transport. Streamable HTTP process,
  authentication and remote cancellation are intentionally deferred.
- Injected timeout proves recovery policy; in-process domain functions are
  synchronous and expected to be non-blocking. Remote client timeouts must be
  tested before deployment.
- Gateway counters are process-local and keyed by trace ID; Phase 3 will bind
  them to a typed dialogue/trajectory state.
- Policy search remains a transparent lexical placeholder, not the Phase 6
  hybrid retrieval implementation.
- Confirmation tokens remain process-local and unauthenticated. They are safe
  for the synthetic local baseline, not a production identity claim.

## Gate result

Phase 2 acceptance criteria pass. Phase 3 must not start until this report and
the Phase 2 commit are reviewed.
