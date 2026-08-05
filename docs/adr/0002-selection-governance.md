# ADR 0002: Evidence-based technology and model selection

- Status: Accepted
- Date: 2026-08-05

## Context

Technology names on a resume invite questions about alternatives, constraints,
and measured trade-offs. Familiarity or popularity is not sufficient evidence.
ServicePilot therefore separates:

1. a **provisional candidate**, which is worth testing;
2. an **accepted choice**, which passed a reproducible comparison;
3. a **deferred choice**, for which the project does not yet have the
   infrastructure or data needed to decide.

Qwen, LangGraph, PostgreSQL, vector stores, inference servers, and training
frameworks are not accepted merely because they appeared in the original
project brief.

## Decision process

Every material dependency or model must have a short ADR containing:

- the capability required by an implemented phase;
- at least two credible alternatives, including the simplest baseline;
- hard constraints and disqualifying conditions;
- a weighted comparison using the same workload and budget;
- primary-source evidence for license and compatibility claims;
- benchmark commands, configuration, raw output, and code/data revisions;
- operational consequences, failure modes, and an exit/migration plan;
- a final status of accepted, rejected, provisional, or deferred.

No candidate may be described as "best" outside the tested workload.

## Technology scoring rubric

Scores run from 1 (poor) to 5 (strong). Hard constraints are evaluated before
weighted scores; a candidate that violates one is rejected regardless of score.

| Criterion | Weight | Evidence |
| --- | ---: | --- |
| Required capability and correctness | 30% | Contract/integration tests on ServicePilot use cases |
| Reliability and observability | 20% | Fault tests, error semantics, trace quality |
| Maintainability and complexity | 15% | Added code/dependencies, API surface, debugging effort |
| Runtime/resource cost | 15% | Measured latency, memory, disk, startup and throughput |
| Ecosystem/compatibility | 10% | Official compatibility matrix and pinned environment test |
| License, security, project health | 10% | Official license, release/security policy, maintained releases |

Hard constraints include local/offline operation, acceptable license, no paid
API dependency, synthetic-data privacy, deterministic testing, and compatibility
with the actual server.

## Current stack decisions and alternatives

| Area | Current status | Why | Alternatives and decision trigger |
| --- | --- | --- | --- |
| Python 3.11 | Accepted target | Current agent/validation ecosystem support while avoiding a dependency on the newest interpreter | 3.12 can replace it after all pinned libraries and GPU wheels pass CI; 3.8 is rejected by planned dependency support |
| Explicit typed state machine | Accepted for deterministic baseline | Transaction transitions, retries, and route changes remain inspectable and unit-testable | Adopt LangGraph only if persisted pause/resume, checkpointing, or graph composition reduces measured complexity without hiding business writes |
| FastAPI + Pydantic | Provisional for API boundary | Typed schemas and OpenAPI suit tool/API contracts | Compare with a thinner ASGI boundary if validation overhead or dependency cost is material; no API framework is needed inside the domain core |
| In-memory repository | Accepted for Phase 1 tests | Removes Docker/database availability from business-rule tests | PostgreSQL becomes the concurrency/integration target after daemon access; SQLite is only a disposable adapter, not concurrency evidence |
| PostgreSQL 16 | Provisional integration target | Transactions, constraints, JSON metadata, and mature concurrency semantics match audit/experiment records | Compare operational complexity with SQLite for local demo and with file-backed stores only where transactional guarantees are unnecessary |
| Official MCP Python SDK | Deferred to Phase 2 | Protocol conformance should not be reimplemented without cause | Pin only after official docs/API review and contract spike; a small internal typed gateway remains the baseline |
| JSONL typed traces | Accepted baseline | Append-friendly, diffable, portable, and usable without a collector | Add OpenTelemetry when cross-service correlation or external observability justifies its operational cost |
| Retrieval stack | Deferred to Phase 6 | Gold evidence and hard negatives must exist before choosing components | Compare lexical-only, dense-only, hybrid, and hybrid+reranker under equal corpus/filter/budget conditions |
| Inference server | Deferred | GPU runtime is currently unusable and workload is not measured | Compare direct Transformers, vLLM, and SGLang on identical model, prompts, concurrency, and output constraints |
| Training framework | Deferred to Phase 9 | Training is forbidden before stable rewards and data | Compare minimal Transformers/PEFT/TRL-style path with specialized distributed frameworks using the real trajectory workload |

## Consequences

This process delays final model and framework branding, but produces defensible
answers: the team can show the rejected alternatives, exact workload, measured
trade-offs, and the condition under which the decision changes. It also prevents
benchmark numbers from unrelated hardware or datasets from being presented as
ServicePilot evidence.

