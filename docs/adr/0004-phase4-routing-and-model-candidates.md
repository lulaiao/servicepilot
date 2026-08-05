# ADR 0004: Phase 4 routing architecture and first model candidate

- Status: Provisional
- Date: 2026-08-05

## Decision

Use an explicit typed `DialogueState` and a deterministic `StatefulRouter` for
the first multi-role baseline. Coordinator, Order, AfterSales, Policy,
Escalation and Verifier share one business policy implementation and differ by
role instruction. Routing runs before every tool call and again after every
tool observation.

Do not add LangGraph yet. The current requirement is fully represented by a
small inspectable state transition, while checkpoint persistence and graph
composition have not been shown to offset another runtime dependency.

Treat the locally cached `Qwen2.5-Coder-1.5B-Instruct` revision
`2e1fd397ee46e1388853d2af2c993145b0f1098a` only as a runnable small-model
candidate. It is not selected: it is code-specialized, the local GPU runtime is
unavailable, and no ServicePilot development-set result exists yet.

## Measured evidence

On the shared 36-scenario deterministic workload, single Agent and dynamic
multi-role execution both reach 36/36 success, 0 false-success and 1.556 mean
tool calls. Multi-role tracing raises mean turns from 5.833 to 8.944 and adds
112 explicit route events. This establishes observability, not a quality gain.

The rule extractor reaches development Macro-F1 0.8333, schema validity 1.0
and high-risk error rate 0.1667. It therefore remains a transparent baseline,
not an accepted language-understanding solution.

## Alternatives

- Static single Agent: cheapest and equally successful on the current catalog,
  but it does not expose responsibility changes after observations.
- LangGraph: deferred until checkpointing, durable pause/resume or graph
  composition becomes a measured need.
- Larger local instruction model: deferred until GPU visibility is repaired
  and identical-budget comparisons can measure quality per memory and latency.
- Cached Qwen Coder 1.5B: useful for an offline compatibility experiment, but
  specialization mismatch and CPU cost may disqualify it.

## Gate

This ADR remains provisional until the local candidate development benchmark
and at least one credible alternative are measured. No sealed result may be
used to tune prompts, rules or select a model.

