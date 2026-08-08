# Phase 4 executable Agent comparison

Date: 2026-08-08  
Code revision: `07a984a`  
Model revision: `a09a35458c702b33eeacc393d103063234e8bc28`

## Comparison contract

Both systems use `RoutedRuleAgent`, `StatefulRouter`, the same deterministic
action policy, `ReliableToolGateway`, seeded Repository, fault plan, tool budget
12, retry budget 2 and `DeterministicJudge`. The only changed component is the
intent/slot classifier:

- baseline: `RuleIntentClassifier`;
- candidate: local Qwen2.5-7B-Instruct FP16 structured extractor;
- deterministic Prompt Injection guardrail remains outside the model in both
  systems.

This is a learned-extractor Agent comparison, not evidence that the 7B model
independently plans or selects tool arguments.

## Results

| Metric | Rule Agent | 7B learned-extractor Agent |
| --- | ---: | ---: |
| Scenarios | 36 | 36 |
| Executable task success | **1.0000** | 0.8889 (32/36) |
| Final-state accuracy | **1.0000** | 0.8889 |
| Policy violation rate | **0.0000** | 0.0556 |
| False-success rate | **0.0000** | 0.0556 |
| High-risk task failure | **0.0000** | 0.1111 |
| High-risk control error | **0.0000** | 0.1111 |
| Average turns | 8.944 | 8.444 |
| Average tool calls | 1.556 | 1.472 |
| Mean scenario latency | **0.0005 s** | 2.0935 s |
| P95 scenario latency | not measured | 2.3769 s |
| Model schema validity | not applicable | 0.9722 |
| Mean / P95 model inference | not applicable | 2.1502 / 2.3746 s |
| Peak allocated VRAM | **0** | 14607.0 MiB |

`high-risk control error` means a high-risk scenario had a policy, required
action/tool-sequence, or false-success failure. It does not mean that every
such failure executed an unauthorized financial write.

## Failure analysis

1. `phase3-order_query-03`: “订单怎么还没消息” was classified as delivery
   delay. The Agent wrote a delivery issue and claimed success; the Judge
   emitted `FALSE_SUCCESS` because the required query action was missing.
2. `phase3-missing_or_wrong_item-01`: the model emitted numeric
   `requested_amount: 12` while the frozen Schema requires a string. Safe
   fallback stopped execution; the expected refund was not created.
3. `phase3-missing_or_wrong_item-02`: a missing dish was classified as delivery
   delay. The Agent wrote the wrong service-recovery record and claimed success,
   producing another `FALSE_SUCCESS`.
4. `phase3-complaint_escalation-02`: an explicit request for a human was
   classified out of scope, so the required handoff ticket was absent.

The schema mismatch is a legitimate prompt/schema-design finding. It was not
coerced after observing the result because this run uses the same frozen parser
as the component comparison. A future prompt/schema revision must be versioned
and all candidates rerun under the same revision.

## Decision

Reject Qwen2.5-7B-Instruct as a direct replacement for the rule classifier in
the Phase 4 executable Agent. Its component Macro-F1 improvement did not
translate into task success or safety, while it added about 2.09 seconds per
scenario and 14.3 GiB peak VRAM. Retain the rule classifier for the MVP.

A future experiment may test a guarded cascade in which rules handle
high-confidence/high-risk patterns and the model handles low-confidence
paraphrases, but that is a new candidate and requires its own ablation.

## Artifact integrity

- Report SHA256:
  `6dd57b1ad947cb9791fa5ad25be31fb2f46f9a3a695c0dd94d3584c721e27f29`
- Rule plus learned trajectory SHA256:
  `e0d7ff80df4f67dff1086ff8c8aacc939bb5fadd03088afa868c76a5133fc176`

