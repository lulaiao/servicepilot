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
candidate. Reject it for the current CPU deployment after the ServicePilot
development benchmark: it is less accurate and substantially more expensive
than the rule baseline. This does not claim that the Qwen2.5 family as a whole
is unsuitable.

## Measured evidence

On the shared 36-scenario deterministic workload, single Agent and dynamic
multi-role execution both reach 36/36 success, 0 false-success and 1.556 mean
tool calls. Multi-role tracing raises mean turns from 5.833 to 8.944 and adds
112 explicit route events. This establishes observability, not a quality gain.

The rule extractor reaches development Macro-F1 0.8333, schema validity 1.0
and high-risk error rate 0.1667. It therefore remains a transparent baseline,
not an accepted language-understanding solution.

The cached Qwen Coder candidate reaches primary accuracy 0.5833, Macro-F1
0.5000, slot exact match 0.3333 and schema validity 0.9167 on the same 12
development examples. Float32 CPU inference averages 12.8405 seconds, has
57.8929-second P95 latency, 0.0779 examples/second throughput and 9378.3 MiB
peak RSS. Its linked snapshot occupies 2.9 GiB. One invalid output used
`unknown` outside the declared enum; four other examples selected an incorrect
primary intent. Raw report SHA256:
`473e5f1252ad3ba2ae95b92667c866b6ac5ef60c85e9428f17a37ddbe8825a02`.

After GPU recovery, the candidate was repeated in FP16 on an RTX A6000 with
one warm-up and three repetitions per development example. Quality was
unchanged; mean/P95 latency became 1.6036/1.9817 seconds and peak allocated
VRAM was 2967.1 MiB. Raw report SHA256:
`9b897befb8ba1fe38601fbeb9acfab6a18b57c56307f7cf368a4f29c3ea23502`.

The smaller general-purpose Qwen2.5-0.5B-Instruct revision
`7ae557604adf67be50417f59c2c2f167def9a775` passed license, offline, schema,
runtime and resource gates. It was nevertheless rejected on quality: all 12
development inputs were classified as `order_query`, yielding Macro-F1 0.0140.
Its lower 965.9 MiB peak allocated VRAM and 1.8602-second P95 latency do not
compensate for that failure.

## Alternatives

- Static single Agent: cheapest and equally successful on the current catalog,
  but it does not expose responsibility changes after observations.
- LangGraph: deferred until checkpointing, durable pause/resume or graph
  composition becomes a measured need.
- Larger local instruction model: deferred until GPU visibility is repaired
  and identical-budget comparisons can measure quality per memory and latency.
- Cached Qwen Coder 1.5B: rejected for this workload and CPU budget. Reconsider
  only with a task-appropriate prompt/model variant and usable GPU runtime.

## Gate

The routing architecture remains provisional until a task-appropriate local
instruction model can be compared on usable GPU hardware. The cached Coder
candidate is rejected. No sealed result may be used to tune prompts, rules or
select a model.
