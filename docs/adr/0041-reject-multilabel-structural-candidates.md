# ADR 0041: Reject both structural multi-label candidates

- Status: Accepted
- Date: 2026-08-13

## Context

After two sealed failures ended the mean-pooling linear-head line, ADR 0040 froze a development-only
comparison between constrained Qwen generation and a BGE cross encoder. Both used the same 128 balanced
v2 dev examples, fixed prompts or label definitions, fixed decoding or threshold, and unchanged quality
and safety gates. No sealed data was accessed.

## Result

The generative candidate achieved macro-F1 0.8698 and complaint false-positive rate 0, but exact-set
accuracy was 0.6953 and complaint recall was 0.5938. It therefore failed two mandatory gates. Mean
latency was 0.9221 seconds and peak allocated VRAM was 14622.76 MiB.

The cross encoder was substantially cheaper at 0.0114 seconds per example and 1107.18 MiB peak VRAM,
but achieved macro-F1 0.3706 and exact-set accuracy 0.2266. It predicted no complaint positives, giving
complaint recall 0. It is rejected on quality regardless of its resource advantage.

The generative parser extracted valid three-boolean objects from all outputs, but all 128 outputs were
wrapped in Markdown fences and none were bare JSON. Thus parser-level schema validity was 1.0 while
strict output-contract adherence was 0. This distinction is retained as a harness finding rather than
silently treating tolerant parsing as full compliance.

## Decision

Reject both candidates. Do not create sealed v3 and do not integrate either component into the Agent.
Stop the secondary-intent enhancement line under the current Phase 9 resource scope. The existing
generative Agent plus deterministic guardrails remains the supported implementation.

Move to Phase 10 delivery work: consolidate runnable demonstrations, Trace Viewer/report entry points,
architecture and failure-analysis documentation, evidence-linked metrics, and honest interview/resume
claims. Future multi-label research requires a separately approved dataset/model budget and a fresh
protocol; it cannot reuse consumed sealed sets.

## Rationale

- Generative output improved precision but did not meet availability and joint-composition gates.
- Zero-threshold reranker relevance is not a competent intent classifier despite attractive cost.
- Weakening thresholds, tuning on dev after seeing results, or creating another sealed set without a
  passing development candidate would undermine the harness methodology.
- Stopping is an evidence-based engineering decision and preserves a strong, reproducible project
  narrative around safety gates and rejected regressions.
