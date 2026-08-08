# Phase 4B Harness Formalization progress

Date: 2026-08-08  
Status: milestone 1 complete; Phase 4B acceptance not yet passed

## Delivered

- Typed `AgentRuntimeHarness` and `EvaluationHarness` boundaries independent
  of a particular model implementation.
- Typed run configuration, session, event, termination, replay, guardrail and
  checkpoint contracts.
- Isolated repository and Gateway assembly for every evaluation trial.
- Compatibility wrappers that keep the Phase 3 evaluation entry points stable.
- Verify-only deterministic replay that has no business-write dependency.
- Completed-session idempotent resume and explicit rejection of unsupported
  running-checkpoint resume.
- Ordered input guardrails and append-only, fingerprinted Harness events.

## Identical-budget comparison

The direct loop and formal Harness used the same 36 scenarios, rule policy,
budgets, faults and deterministic Judge. Timings are ten paired repetitions
with direct-first and Harness-first order alternated to reduce ordering bias.

| Metric | Direct loop | Formal Harness |
| --- | ---: | ---: |
| Executable success | 36/36 | 36/36 |
| Final-state accuracy | 1.0 | 1.0 |
| Policy-violation rate | 0 | 0 |
| False-success rate | 0 | 0 |
| Average turns | 8.944 | 8.944 |
| Average tool calls | 1.556 | 1.556 |
| Mean suite latency | 0.021923 s | 0.031774 s |
| P95 suite latency | 0.029227 s | 0.051376 s |

All authoritative judgments were identical. Mean paired absolute overhead was
0.009850 seconds per 36-scenario suite, or 0.2736 milliseconds per scenario.
This is an in-process deterministic microbenchmark, not a model-serving
latency claim.

The final formal run produced 36 completed sessions, 72 runtime events and 36
verify-only replay sessions. Unit tests additionally assert that replay does
not change the repository audit-event count.

## Reproduction and provenance

```text
PYTHONPATH=src .venv/bin/python scripts/run_phase4b_harness_eval.py \
  --code-revision 2bf0cae \
  --repetitions 10 \
  --output artifacts/reports/phase4b_harness_comparison.json \
  --trace-output artifacts/traces/phase4b_harness_trajectories.jsonl
```

- Code revision: `2bf0cae`
- Scenario SHA-256:
  `ea33cccc96eec2a877f204c00441ad73a6b8545784f39e98cdd55a8081e2cead`
- Report SHA-256:
  `2332c5ca9d24976778341ccc89511548aebf3da97f6f6466838e236c2cca91cb`
- Trace SHA-256:
  `3ad8a03fb3e2d8dbd3137e897e8954353752e4579135678079c605a65608f986`
- Tracked manifest: `experiments/manifests/phase4b_harness_comparison.json`

## Open acceptance work

- Add tool-intercepting dispatch so tool guardrails and per-step checkpoints
  surround every material tool call.
- Resume an interrupted running session without repeating a committed
  high-risk write; completed-session resume alone is insufficient.
- Wire and test explicit termination/recovery for turn, tool, retry, time and
  token budgets, missing confirmation and version conflict.
- Run the required tool-budget, input-guardrail, observation-rerouting and
  external-Verifier ablations.
- Add failure isolation and resumable experiment manifests; bounded
  concurrency remains deferred until it has a measured need.

ADR 0005 therefore remains **Proposed**, and the project must not claim full
Phase 4B acceptance or durable tool-level recovery yet.
