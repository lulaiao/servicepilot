# Phase 4 GPU structured-extractor comparison

Date: 2026-08-08  
Status: small-candidate comparison complete; medium candidate pending

## Fixed protocol

- Role: intent, secondary-intent and slot structured extraction.
- Data: 12 development examples; sealed test was not used.
- Prompt and schema: identical for every candidate.
- Decoding: greedy, batch size 1, maximum 128 new tokens.
- Runtime: PyTorch 2.5.1+cu121, CUDA 12.1, RTX A6000.
- Precision: FP16.
- Measurement: one warm-up followed by three repetitions per example.
- Seed: 20260805.
- Every repetition produced the same output for both candidates.

## Results

| Candidate | Rule baseline | Qwen2.5-0.5B-Instruct | Qwen2.5-Coder-1.5B-Instruct |
| --- | ---: | ---: | ---: |
| Revision | n/a | `7ae557604adf67be50417f59c2c2f167def9a775` | `2e1fd397ee46e1388853d2af2c993145b0f1098a` |
| Primary accuracy | 0.8333 | 0.0833 | 0.5833 |
| Macro-F1 | 0.8333 | 0.0140 | 0.5000 |
| Schema valid | 1.0000 | 1.0000 | 0.9167 |
| Secondary exact | 1.0000 | 0.0000 | 0.5833 |
| Slot exact | 1.0000 | 0.0833 | 0.3333 |
| Mean latency | not applicable | 1.4928 s | 1.6036 s |
| P95 latency | not applicable | 1.8602 s | 1.9817 s |
| Examples/s | not applicable | 0.6699 | 0.6236 |
| Generation tokens/s | not applicable | 83.8496 | 57.9429 |
| Peak allocated VRAM | 0 | 965.9 MiB | 2967.1 MiB |

The 0.5B instruction model predicted `order_query` for all 12 examples. This is
a deterministic mode-collapse failure under the fixed zero-shot prompt, not a
schema parsing failure. The Coder model produced a broader label distribution
but remained below the rule baseline and emitted one invalid enum value.

## Artifact integrity

- Qwen2.5-0.5B-Instruct raw report SHA256:
  `4f0ae43a487666a5373a5cabf3ac2ff6a40a696d763d081bb8fc9ec275d31bef`
- Qwen2.5-0.5B-Instruct derived metrics SHA256:
  `7957432d9ce83abe25f830dce6730ed9d03e250131153750f0ca3b303d1f2098`
- Qwen2.5-Coder-1.5B-Instruct raw report SHA256:
  `9b897befb8ba1fe38601fbeb9acfab6a18b57c56307f7cf368a4f29c3ea23502`
- Qwen2.5-Coder-1.5B-Instruct derived metrics SHA256:
  `00dd5f964e16fe5aa0d64e699963611d4ebafb2e09ff4833d96252f8f5cf2320`

Raw outputs remain under ignored `artifacts/reports/` and include per-example,
per-repetition latency, exact outputs, runtime metadata and peak memory.

## Decision

Reject both measured learned candidates for this extractor role. Retain the
rule baseline provisionally. A task-appropriate medium instruction model must
be evaluated before the Phase 4 model-selection gate can close. Few-shot or
prompt tuning may be studied on train data later, but must be applied equally
to surviving candidates and may not use sealed examples.

