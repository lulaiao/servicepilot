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

## GPU re-audit and formal model comparison

On 2026-08-08, multiple RTX A6000 cards were available. PyTorch 2.5.1+cu121
successfully executed FP16 and BF16 CUDA smoke tests. The benchmark now records
warm-up, repetitions, synchronized GPU latency, tokens/s, peak allocated and
reserved VRAM, GPU identity, seed and exact runtime configuration.

The earlier CPU result remains historical evidence. The formal FP16 GPU result
for cached Qwen2.5-Coder-1.5B-Instruct uses three repetitions per development
example:

| Metric | Result |
| --- | ---: |
| Primary accuracy | 0.5833 |
| Macro-F1 | 0.5000 |
| Slot exact match | 0.3333 |
| Schema validity | 0.9167 |
| Mean / P95 latency | 1.6036 s / 1.9817 s |
| Throughput | 0.6236 examples/s |
| Peak allocated VRAM | 2967.1 MiB |

This candidate is rejected for the extractor role because it is worse than the
rule baseline on quality despite acceptable GPU latency and memory. The result
does not reject other Qwen variants.

Qwen2.5-0.5B-Instruct revision
`7ae557604adf67be50417f59c2c2f167def9a775` was then evaluated under the
identical protocol. It used only 965.9 MiB peak allocated VRAM and reached
1.8602-second P95 latency, but predicted `order_query` for every example:
primary accuracy 0.0833 and Macro-F1 0.0140. It is rejected. Full comparison
and artifact hashes are in `phase4_gpu_model_comparison.md`.

The remaining blocker is no longer GPU availability. Phase 4 still requires a
task-appropriate medium instruction candidate and an end-to-end learned-model
comparison. Downloading that candidate requires the separate model resource
budget specified by the project plan.

## Reproduction

```text
PYTHONPATH=src .venv/bin/python scripts/run_phase4_routing_eval.py
PYTHONPATH=src .venv/bin/python scripts/analyze_model_benchmark.py \
  --input artifacts/reports/qwen25_coder_1_5b_cuda_fp16_dev_r3.json \
  --output artifacts/reports/qwen25_coder_1_5b_cuda_fp16_dev_r3_metrics.json
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy src/servicepilot
```

Phase 4 remains open until a medium candidate and learned end-to-end Agent are
compared or explicitly deferred with resource evidence.
