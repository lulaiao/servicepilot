# Phase 4B Harness Formalization progress

Date: 2026-08-08  
Status: milestone 3 complete; Phase 4B acceptance not yet passed

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
- TOOL-stage Guardrail enforcement before Gateway dispatch, with every
  decision persisted in the corresponding tool-step Checkpoint.
- Explicit `tool_budget_exhausted`, `retry_budget_exhausted`,
  `time_budget_exhausted`, `turn_budget_exhausted` and
  `token_budget_exhausted` termination reasons and usage counters.

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

## TOOL Guardrail and budget regression

TOOL decisions execute before Gateway dispatch. The blocking test targets
`create_refund_request`, records the rejecting guardrail in a `BLOCKED` tool
Checkpoint and proves the Repository contains zero refunds. Allowed decisions
are also stored with `STARTED` and `COMMITTED` steps.

The Harness has distinct tested termination paths for:

- tool calls: Dispatcher stops before the call that would exceed the limit;
- retries: a retryable ToolResult that exhausts the configured Gateway retry
  allowance terminates with the observed retry count;
- time: `asyncio.timeout` bounds the full Agent run;
- turns: authoritative user/assistant events are counted from the trajectory;
- tokens: the injected model/Agent reports actual `model_tokens_used`; the
  deterministic rule Agent reports zero rather than an estimated value.

Turn and token checks occur when the Agent returns a trajectory. They classify
and reject an over-budget result but cannot pre-empt a monolithic model call;
streaming adapters must enforce their own generation cap as well.

After these controls were added, a ten-repetition regression retained 36/36
success and identical direct-loop/Harness Judge outcomes. The Harness emitted
184 events and measured 0.3181 ms mean overhead per scenario.

- Code revision: `3ac510c`
- Report SHA-256:
  `4cd18c0692802348a4edaa39323b7a48f206f539b3930bb9192b54ceb7b8303b`
- Trace SHA-256:
  `395d55076dfea9afe7dd8aedd5a86dd73b2071f77394363f10b891a868b081a3`
- Manifest: `experiments/manifests/phase4b_budget_guardrail_regression.json`

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

- Add Harness-level recovery classifications for missing confirmation and
  version conflict; these are currently typed Gateway results handled by the
  Agent policy rather than Harness termination reasons.
- Add failure isolation and resumable experiment manifests; bounded
  concurrency remains deferred until it has a measured need.

ADR 0005 remains **Proposed** until missing-confirmation/version-conflict
recovery and evaluation failure isolation are formalized. TOOL Guardrails and
the five requested budget paths are now implemented and tested.
