# Evaluation protocol

## Phase 3 executable baseline

The catalog contains 36 scenarios: three language/fault variants for each of 12
intent classes. Scenarios are immutable Pydantic records defining initial
business state, user utterance, information disclosure, allowed/forbidden
actions, gold policy evidence, deterministic faults and expected final state.

The FSM user reveals the order ID only after a clarification, supplies refund or
reschedule details when asked, confirms explained high-risk previews, and can
refuse confirmation. It never calls tools or evaluates success.

Each trajectory stores ordered user, assistant and tool events; tool arguments;
typed results; trace ID; detected intents; final message; and whether the Agent
claimed completion. Raw trajectories use JSONL.

## Deterministic Judge

The Judge reads the Repository after execution and checks:

- order, refund, coupon, delivery issue, handoff and schedule state;
- required and forbidden tool calls;
- policy evidence IDs returned by previews;
- whether completion was claimed despite incorrect final state.

`task_success` requires correct final state, valid action sequence and sufficient
gold evidence. `false_success` is true only when the Agent claims success while
authoritative state is wrong. Agent prose never overrides these assertions.

## Reproduction

```bash
PYTHONPATH=src .venv/bin/python scripts/run_eval.py
```

This writes the report, scenario hash manifest and raw trajectories under
`artifacts/`. The tracked Phase 3 manifest records the fixed hash.

## Interpretation limit

Phase 3 scenarios are a deterministic development catalog designed around the
rule baseline. Its score measures executable integration correctness, not
language generalization. Phase 4 must create frozen train/dev/sealed-test splits
before comparing learned models or multi-Agent routing.
