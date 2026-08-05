# Phase 4 progress report

Date: 2026-08-05  
Status: in progress; model-selection gate not passed

## Delivered

- Frozen 60-example intent/slot catalog: 24 train, 12 development and 24
  sealed-test records.
- Typed intent, slot, risk, dialogue-state, observation and route contracts.
- Deterministic intent baseline with Prompt Injection blocking.
- Observation-driven Coordinator, Order, AfterSales, Policy, Escalation and
  Verifier routing.
- Same-policy, same-scenario, same-tool-budget single-versus-routed comparison.
- Offline local-model benchmark command pinned to an exact model revision.

## Actual deterministic results

| Metric | Single Agent | Dynamic multi-role |
| --- | ---: | ---: |
| Executable success | 36/36 | 36/36 |
| Final-state accuracy | 1.0 | 1.0 |
| False-success rate | 0 | 0 |
| Mean tool calls | 1.556 | 1.556 |
| Mean turns | 5.833 | 8.944 |

The routed run emitted 112 route/reroute events (3.111 per scenario). It has
not demonstrated a business-success improvement over the simpler baseline.

Rule-extractor development results: primary accuracy 0.8333, Macro-F1 0.8333,
slot exact match 1.0, schema validity 1.0 and high-risk error rate 0.1667.

## Holdout handling

During initial harness validation, the sealed split was accidentally included
in one baseline report before model selection. No rule or prompt was changed
from that output. The runner now excludes sealed data by default and requires
an explicit `--include-sealed` flag. The incident is recorded so the early
result is not represented as an untouched final holdout; model candidates use
development data only.

## Current blocker

`nvidia-smi` cannot communicate with the driver and
`torch.cuda.is_available()` is false. A one-example float32 CPU smoke using the
cached 1.5B candidate did not finish within 90 seconds and was stopped. This is
runtime evidence against casually selecting that model, but not a quality
result.

## Reproduction

```text
PYTHONPATH=src .venv/bin/python scripts/run_phase4_routing_eval.py
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src/servicepilot
```

Phase 4 remains open until the development benchmark is completed and compared
with another viable candidate or a documented resource-based deferral.
