# Phase 4 GPU structured-extractor comparison

Date: 2026-08-08  
Status: component comparison complete; end-to-end validation pending

## Fixed protocol

- Role: intent, secondary-intent and slot structured extraction.
- Data: 12 development examples; sealed test was not used.
- Prompt and schema: identical for every candidate.
- Decoding: greedy, batch size 1, maximum 128 new tokens.
- Runtime: PyTorch 2.5.1+cu121, CUDA 12.1, RTX A6000.
- Precision: FP16.
- Measurement: one warm-up followed by three repetitions per example.
- Seed: 20260805.
- Every repetition produced the same output for all candidates.

## Results

| Candidate | Rule | Qwen 0.5B | Qwen Coder 1.5B | Qwen 7B |
| --- | ---: | ---: | ---: | ---: |
| Primary accuracy | 0.8333 | 0.0833 | 0.5833 | **0.9167** |
| Macro-F1 | 0.8333 | 0.0140 | 0.5000 | **0.8909** |
| Schema valid | 1.0000 | 1.0000 | 0.9167 | 1.0000 |
| Secondary exact | 1.0000 | 0.0000 | 0.5833 | 1.0000 |
| Slot exact | **1.0000** | 0.0833 | 0.3333 | 0.5833 |
| High-risk error | 0.1667 | 1.0000 | 0.1667 | 0.1667 |
| Mean latency | n/a | 1.4928 s | 1.6036 s | 2.1881 s |
| P95 latency | n/a | 1.8602 s | 1.9817 s | 2.4452 s |
| Examples/s | n/a | 0.6699 | 0.6236 | 0.4570 |
| Peak allocated VRAM | 0 | 965.9 MiB | 2967.1 MiB | 14607.5 MiB |

The 0.5B instruction model predicted `order_query` for all 12 examples. This is
a deterministic mode-collapse failure under the fixed zero-shot prompt, not a
schema parsing failure. The Coder model produced a broader label distribution
but remained below the rule baseline and emitted one invalid enum value.
The 7B instruction model made one primary-intent error: it classified a
missing-item request as delivery delay. It improved intent metrics over the
rule baseline but did not improve the high-risk error rate and had weaker
strict slot matching.

## Artifact integrity

- Qwen2.5-0.5B-Instruct raw report SHA256:
  `4f0ae43a487666a5373a5cabf3ac2ff6a40a696d763d081bb8fc9ec275d31bef`
- Qwen2.5-0.5B-Instruct derived metrics SHA256:
  `9b26ae934f2c34faf3b62a2d533b28991ad2fbc51c0933ae4fc829a24f0f370c`
- Qwen2.5-Coder-1.5B-Instruct raw report SHA256:
  `9b897befb8ba1fe38601fbeb9acfab6a18b57c56307f7cf368a4f29c3ea23502`
- Qwen2.5-Coder-1.5B-Instruct derived metrics SHA256:
  `7e3d30578c4b863630f49ec4482ca325d82d6036d62ba3a50fd06f96c88f3d53`
- Qwen2.5-7B-Instruct raw report SHA256:
  `0da31edf8673205ce5f3ea56c2bc36b539c72407f27e7161d054466ac0ce690f`
- Qwen2.5-7B-Instruct derived metrics SHA256:
  `be4ab873095d460acc270c003c0a2c6bd09e9c7d41905650df8892dfb928b48c`

Raw outputs remain under ignored `artifacts/reports/` and include per-example,
per-repetition latency, exact outputs, runtime metadata and peak memory.

## Decision

Reject the 0.5B and Coder 1.5B candidates for this extractor role. Promote the
7B instruction model to an **end-to-end candidate**, not an accepted choice:
it improves development intent metrics and passes the schema gate, but does not
improve high-risk error rate, has weaker strict slot matching, and has not yet
shown an executable task-success gain that justifies 14.3 GiB peak VRAM.
Retain the rule extractor as the deployed baseline until that comparison.
