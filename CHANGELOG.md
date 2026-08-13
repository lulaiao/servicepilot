# Changelog

## [0.1.0rc1] - 2026-08-13

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
- Five official MCP SDK v2 servers exposing 22 strongly validated business
  tools with structured output and in-memory protocol contract tests.
- Reliable Agent-side Gateway with trace IDs, latency, summaries, call budgets,
  bounded exponential retry, stable error codes and deterministic fault plans.
- Rescheduling, delivery issue and handoff ticket domain capabilities.
- Timeout, transient, empty, partial, lost-response and version-conflict
  recovery tests.
- Phase 3 immutable scenario, trajectory, Judge and aggregate report schemas.
- FSM user simulator with progressive slot disclosure and confirmation refusal.
- Rule-based single-Agent baseline covering 12 intent classes and multi-intent
  execution.
- Deterministic 36-scenario catalog with language and transient-fault variants.
- Executable final-state, policy evidence, forbidden-action and false-success
  Judge.
- Reproducible JSONL trajectory/report/manifest generation command.
- Phase 10 CPU portfolio demo, self-contained Trace Viewer and validated
  evidence index.
- Clean archived-source CPython 3.11 acceptance with 261 passing tests.
- Apache-2.0 license, contribution/security guidance and release checklist.
- Deterministic release-readiness checker for package/license metadata and
  tracked sensitive-file boundaries.
- Least-privilege GitHub Actions quality matrix, Dependabot configuration, and
  contribution templates for public-repository handoff.
- Public GitHub repository metadata and private security-advisory routing.
- First hosted GitHub quality matrix accepted on Python 3.11 and 3.12.
- Phase 10 public-delivery status and 13-entry release checklist reconciled with
  the latest hosted workflow evidence.
- Protected RC PR #2 merge and hosted Python 3.11/3.12 evidence recorded before
  tag creation.

### Verification

- `make smoke`: passed (1 test) with the host's dependency-free Python 3.8
  bootstrap runtime.
- `PYTHONPATH=src python3 -m compileall -q src tests`: passed.
- Phase 1 `make test` with Python 3.11.15: 26 tests passed.
- Phase 1 `ruff check src tests`: passed.
- Phase 1 strict MyPy analysis: 23 source files passed.
- Phase 2 full suite: 42 tests passed.
- Phase 2 Ruff and strict MyPy analysis: 29 source files passed.
- Phase 3 fixed development catalog: 36/36 executable tasks succeeded; final
  state accuracy 100%, policy violations 0%, false-success 0%.
- Phase 3 full test suite: 50 tests passed before final documentation update.
- Phase 10 clean-source suite: 261 tests, Ruff over source/tests/scripts and
  strict MyPy over 109 source files passed.

[0.1.0rc1]: https://github.com/lulaiao/servicepilot/releases/tag/v0.1.0-rc1
