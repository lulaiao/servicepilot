# ADR 0001: Core stack and phased dependency policy

- Status: Accepted for Phase 0
- Date: 2026-08-05

## Context

ServicePilot needs deterministic transactional evaluation before it needs model
orchestration. The current host exposes Python 3.8 only, cannot access the
Docker daemon, and has an unusable NVIDIA management runtime. Introducing a
large agent framework now would hide state transitions and make the MVP depend
on unresolved infrastructure.

## Decision

- Target Python 3.11 and use a user-owned virtual environment.
- Use FastAPI and Pydantic 2 for the eventual gateway and boundary schemas.
- Implement routing as an explicit typed state machine first. Reconsider
  LangGraph only after the deterministic baseline demonstrates a concrete need
  for graph persistence or interrupt/resume semantics.
- Use the official Python MCP SDK in Phase 2, pinning its exact tested version
  then because its live API has not yet been verified in this offline audit.
- Keep Phase 1 persistence behind repository interfaces with an in-memory
  implementation. PostgreSQL 16 becomes the integration target when Docker or
  another local database endpoint is available. Redis is not an MVP dependency.
- Start policy retrieval with a transparent lexical baseline. Add dense
  retrieval and reranking only in Phase 6, after gold evidence IDs exist.
- Start inference with a deterministic rule/MockModel boundary. Model selection
  requires a fresh license, disk, context, CUDA, and GPU compatibility audit.
- Use JSONL traces with stable typed event schemas before adding OpenTelemetry.
- Use pytest, Ruff, and strict MyPy once Python 3.11 dependencies can be
  installed. Retain a standard-library smoke test for bootstrap diagnosis.

## Consequences

The first business phases remain runnable without Docker, GPU, network, or paid
services. Explicit state and repository interfaces increase initial modeling
work but make idempotency, optimistic locking, and executable evaluation easy to
test. Some final dependency versions and both MCP/model choices remain deferred
and must receive their own ADRs before use.

## Rejected alternatives

- **Immediate LangGraph adoption:** deferred because it adds a framework before
  the required transition and recovery semantics are proven.
- **PostgreSQL as a Phase 1 hard dependency:** rejected because current Docker
  permissions would make core tests unavailable.
- **SQLite as production architecture:** rejected as the final concurrency
  target, though a disposable adapter may be useful for local tests.
- **Immediate local-model download:** rejected by the Phase 0 boundary and
  unresolved GPU/runtime audit.
- **Paid hosted model APIs:** rejected by privacy and cost requirements.

