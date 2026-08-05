# Changelog

## Unreleased

### Added

- Phase 0 host feasibility audit and core-stack ADR.
- Gated implementation plan and repository contribution constraints.
- Initial configuration, packaging, Docker Compose placeholder, and module
  boundaries.
- Dependency-free package health check and smoke test.
- Evidence-based technology selection governance, explicit decision matrix, and
  a role-specific model selection protocol.
- Clarified that Qwen model names from the brief are provisional candidates,
  not accepted choices.
- Phase 1 immutable domain records for orders, payments, refunds, coupons,
  merchants, deliveries, policy decisions, previews, and audit events.
- Explicit order state machine and versioned natural-language/executable
  policies.
- Thread-safe in-memory repository contract, deterministic synthetic generator,
  and preview-confirm-execute transaction service.
- Request-bound one-time confirmations, optimistic concurrency, action-scoped
  idempotency, and concurrent duplicate-write coverage.

### Verification

- `make smoke`: passed (1 test) with the host's dependency-free Python 3.8
  bootstrap runtime.
- `PYTHONPATH=src python3 -m compileall -q src tests`: passed.
- Phase 1 `make test` with Python 3.11.15: 26 tests passed.
- Phase 1 `ruff check src tests`: passed.
- Phase 1 strict MyPy analysis: 23 source files passed.
