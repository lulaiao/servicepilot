# ADR 0005: Formalize an internal Agent and evaluation Harness

- Status: Accepted
- Date: 2026-08-08

## Context

ServicePilot already has an executable Agent loop, reliable tool Gateway,
typed routing state, FSM user simulator, deterministic Judge, fault injection,
traces and reports. These capabilities are split across concrete Phase 3 and
Phase 4 implementations. Memory, retrieval, monitoring and additional models
would otherwise depend directly on those implementations.

“Agent Harness” is not treated as a library brand. It is the runtime boundary
that processes inputs, coordinates model/tool interactions and returns results.
The evaluation Harness separately runs trials and grades outcomes.

## Decision

Add Phase 4B and first implement lightweight internal typed Harness contracts.
Preserve compatibility wrappers for the existing Phase 3 runner while moving
environment assembly and execution ownership behind the new boundaries.

Keep the deterministic Judge outside the Agent Runtime Harness. Keep all
business authorization in the domain service and Gateway. A Harness
guardrail may stop or reroute an action but may not authorize a write.

## Alternatives

### Keep the current concrete runner

Lowest immediate effort, but model, memory, routing and evaluation experiments
would share assembly logic and make ablations harder to reproduce.

### Adopt LangGraph immediately

It offers graph and checkpoint concepts, but ServicePilot has not yet measured
a need that offsets dependency, persistence and debugging complexity. Deferred
until compared against the internal Harness.

### Adopt Inspect as the only Harness

Inspect is a credible external evaluation framework with Agent, MCP and custom
tool support. It does not replace ServicePilot's transactional runtime,
confirmation protocol or authoritative domain Judge. Consider an adapter in
Phase 7 rather than coupling the Phase 4 runtime to it.

## Consequences

- More explicit interfaces and initially some adapter code.
- Reproducible model/runtime substitutions and Harness ablations.
- Resume, replay and overhead become testable claims rather than implicit
  behavior.
- The resume may mention Agent Harness only after Phase 4B acceptance evidence
  exists.

## Acceptance evidence

The internal Harness passed the Phase 4B gate:

- 36/36 identical authoritative outcomes against the direct loop;
- verify-only replay with zero Repository writes;
- typed tool-step recovery without repeating a committed refund after a lost
  response;
- explicit Prompt Injection, confirmation, version-conflict and budget paths;
- TOOL-stage Guardrails before Gateway dispatch;
- four required ablations and measured overhead;
- bounded concurrency, per-Trial failure isolation and durable resume that
  skips completed Trials.

Evidence is linked from `experiments/reports/phase4b_harness_progress.md` and
the three tracked Phase 4B manifests. This accepts the lightweight internal
boundary, not an external Harness framework and not a claim that every future
model adapter is automatically safe.
