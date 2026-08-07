# Agent and evaluation Harness design

## Meaning in ServicePilot

ServicePilot uses **Agent Harness** to mean the model-independent runtime that
turns a policy/model into an executable Agent by managing state, tools,
guardrails, budgets, tracing and termination. It uses **Evaluation Harness** to
mean the infrastructure that creates trials, runs the Agent Harness, grades the
authoritative outcome and aggregates reproducible results.

This distinction follows the terminology described in Anthropic's
“Demystifying evals for AI agents”:
https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

`Agent Harness` is an architecture boundary, not the name of a dependency.

## Boundary

```text
Scenario/User input
        |
        v
AgentRuntimeHarness
  Session + typed state + budgets
  Input/Tool/Output Guardrails
  ModelAdapter -> Router -> role policy
  ToolDispatcher -> ReliableToolGateway -> MCP
  CheckpointStore + append-only HarnessEvent trace
        |
        v
Trajectory + termination + resource usage
        |
        v
EvaluationHarness
  isolated seeded environment
  FSM user simulator
  authoritative Repository snapshot
  DeterministicJudge
  manifest + aggregate report
```

The domain service remains the only write authority. The Runtime Harness may
dispatch a write but cannot bypass preview, confirmation, idempotency or
version checks. The Evaluation Harness and Judge remain read-only consumers of
final business state.

## Why formalize now

Phase 3 proved the deterministic business loop. Phase 4 added typed dialogue
state, observation-driven routing and model comparisons. Without a Harness
boundary, model code, routing, tool execution and experiment assembly would
become coupled as new memory, retrieval and Monitor capabilities arrive.

Formalization provides stable substitution points for:

- rule policy versus local structured-output models;
- single-Agent versus dynamic multi-role routing;
- in-process Registry versus MCP transport;
- no-memory versus layered-memory experiments;
- live execution versus deterministic replay;
- internal evaluation versus a future external evaluator adapter.

## Non-goals

- Do not introduce LangGraph merely to obtain a Harness label.
- Do not let an LLM Judge replace authoritative business-state assertions.
- Do not copy model weights for each role.
- Do not claim durable resume until checkpoint and committed-write recovery
  tests pass.
- Do not place policy authorization inside prompts.

## Framework decision

The first implementation is a lightweight internal Harness because the
existing typed contracts and deterministic Judge are domain-specific and
already operational. Inspect may be evaluated as an external evaluation
adapter in Phase 7 because it supports agent evaluations, MCP and custom tools:
https://inspect.aisi.org.uk/

LangGraph or another runtime framework remains deferred until durable
checkpointing or graph composition demonstrates lower implementation and
operational cost than the internal baseline.

## Evidence required for resume claims

A Harness resume statement is permitted only after the following artifacts
exist:

- accepted Harness ADR;
- direct-loop versus Harness report;
- guardrail/rerouting/verifier ablations;
- replay and interrupted-write recovery tests;
- raw trace and Manifest hashes;
- measured overhead and failure analysis.

