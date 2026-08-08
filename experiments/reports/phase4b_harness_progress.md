# Phase 4B Harness Formalization progress

Date: 2026-08-08  
Status: milestone 2 complete; Phase 4B acceptance not yet passed

## Delivered

- Typed `AgentRuntimeHarness` and `EvaluationHarness` boundaries independent
  of a particular model implementation.
- Typed run configuration, session, event, termination, replay, guardrail and
  checkpoint contracts.
- Isolated repository and Gateway assembly for every evaluation trial.
- Compatibility wrappers that keep the Phase 3 evaluation entry points stable.
- Verify-only deterministic replay that has no business-write dependency.
- Completed-session idempotent resume plus safe interrupted-session resume from
  persisted tool steps.
- Ordered input guardrails and append-only, fingerprinted Harness events.
- Transparent tool interception with started/committed step checkpoints and
  cached-result replay keyed by tool, argument fingerprint and call ordinal.

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

## Lost-response recovery evidence

The high-risk recovery test injects `LOST_RESPONSE` for
`create_refund_request`. The domain write commits on the first Gateway attempt;
the same idempotency key makes the Gateway retry return the original result on
attempt two. The Dispatcher then persists that result and a simulated process
interruption occurs before the Agent receives it.

On resume, the Agent control flow restarts but the Dispatcher returns the
persisted tool result instead of calling the Gateway again. Assertions prove
there is still exactly one refund, the Repository audit-event sequence is
unchanged after resume, and the session reaches `COMPLETED`. This evidence is
implemented by
`test_resume_after_checkpointed_high_risk_write_does_not_repeat_refund`.

## Four Harness ablations

All ablations use the same 36 scenarios and deterministic Judge.

| Ablation | Result | Interpretation |
| --- | --- | --- |
| Tool budget 12 → 1 | success 1.0000 → 0.3611 | One call cannot complete preview/confirm/write workflows. |
| Input guardrail off | enabled blocks 1/1 injection before tools; disabled policy remains safe | The policy is a redundant second boundary. |
| Observation rerouting off | 56 → 0 reroute events; success unchanged at 1.0000 | Current fixed catalog shows observability but no quality gain. |
| External Verifier off | claim-only disagrees on 4/36 and falsely rejects four valid outcomes | Agent prose is not an authoritative success signal. |

Reproduction:

```text
PYTHONPATH=src .venv/bin/python scripts/run_phase4b_harness_ablations.py \
  --code-revision 569e655 \
  --output artifacts/reports/phase4b_harness_ablations.json
```

- Ablation report SHA-256:
  `db5fa8a5ba1642b8649d1159cd3b5ccab034e779b8dcd9cf085235b3cb12f81d`
- Tracked manifest: `experiments/manifests/phase4b_harness_ablations.json`
- GPU required: no. These controlled deterministic-policy ablations are CPU
  experiments; adding the 7B model would change the tested variable.

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

- Wire and test explicit termination/recovery for turn, tool, retry, time and
  token budgets, missing confirmation and version conflict.
- Apply TOOL-stage guardrail decisions to intercepted calls; the interception
  and checkpoints exist, but only INPUT and OUTPUT decisions are enforced.
- Add failure isolation and resumable experiment manifests; bounded
  concurrency remains deferred until it has a measured need.

ADR 0005 therefore remains **Proposed** until the remaining budget/termination
and TOOL-guardrail paths pass. The narrow lost-response recovery claim above is
now supported; a general durable-runtime claim is not.
