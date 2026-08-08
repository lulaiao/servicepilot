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

Qwen2.5-7B-Instruct revision
`a09a35458c702b33eeacc393d103063234e8bc28` passes the Apache-2.0, offline,
runtime and resource hard gates on one RTX A6000. On development data it reaches
Macro-F1 0.8909 and schema validity 1.0, exceeding the rule baseline's 0.8333
Macro-F1. However, strict slot exact match is 0.5833 versus the rule baseline's
1.0, high-risk error remains 0.1667, P95 latency is 2.4452 seconds and peak
allocated VRAM is 14607.5 MiB. It is promoted to an end-to-end candidate, not
accepted for deployment.

The executable comparison at code revision `07a984a` changes only the
classifier inside the same routed Agent and uses the same 36 scenarios,
budgets, tools and deterministic Judge. The rule Agent succeeds on 36/36 with
zero policy violation and false-success. The 7B learned-extractor Agent reaches
32/36 (0.8889), with 0.0556 policy violation, 0.0556 false-success and 0.1111
high-risk control error. Mean scenario latency is 2.0935 seconds and peak
allocated VRAM is 14607.0 MiB. Therefore the 7B candidate is rejected as a
direct replacement despite its stronger component Macro-F1.

## Alternatives

- Static single Agent: cheapest and equally successful on the current catalog,
  but it does not expose responsibility changes after observations.
- LangGraph: deferred until checkpointing, durable pause/resume or graph
  composition becomes a measured need.
- Qwen2.5-7B-Instruct: rejected as a direct rule-classifier replacement after
  identical-budget executable Agent evaluation.
- Cached Qwen Coder 1.5B: rejected for this workload and CPU budget. Reconsider
  only with a task-appropriate prompt/model variant and usable GPU runtime.

## Gate

The explicit router and rule classifier remain the accepted Phase 4 MVP
baseline. All measured learned extractor candidates are rejected for direct
deployment. No sealed result may be used to tune a future cascade, prompt or
schema revision.
