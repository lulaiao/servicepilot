# Phase 6 acceptance: policy retrieval and transactional evidence gate

Date: 2026-08-08  
Status: Accepted

## Accepted design

- Primary GPU pipeline: metadata filter -> M3 dense top six -> plain-query
  BGE-v2-M3 cross-encoder -> per-query min-max normalization -> fixed 0.5/0.5
  score fusion -> top three.
- CPU fallback: BM25 with metadata filtering.
- Transaction policy: required policy evidence must be complete before the
  Agent enters preview/confirm/execute; incomplete evidence fails closed and
  produces an auditable `search_policy` event.

## Sealed result

The 36-query set and evaluator were committed at `cd7f76e` before model
execution. No candidate depth, weight, threshold, input format or label was
changed after the run.

| Candidate | Recall@3 | MRR@3 | nDCG@3 | Required top-1 | Contradictory top-1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| M3 dense-only | 0.9861 | 0.9722 | 0.9683 | 0.9444 | 0.0000 |
| Plain k6 fixed fusion | 0.9861 | 0.9861 | 0.9807 | 0.9722 | 0.0000 |

Fusion wins ranking and primary-evidence accuracy without changing candidate
coverage or contradictory rank-one errors. It adds 8.2225 ms/query reranker
latency and raises total pipeline peak allocated VRAM to 2,199.74 MiB.

## Transactional Agent result

After normalizing domain-enum metadata casing, the locked fusion pipeline
retrieves complete required evidence for 21/21 policy-sensitive scenarios.

| Variant | Task success | Final state | Policy violations | False-success | Avg tools |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rule Agent | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 1.556 |
| Retrieval-gated Agent | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 2.139 |

The baseline was already perfect, so retrieval does not claim a task-success
increase. Its measured value is an additional fail-closed evidence boundary:
the missing-evidence regression test leaves the order unchanged and emits no
transaction write. Integration preserves all existing business success at the
cost of one policy-search tool event on policy-sensitive scenarios.

## Failure found and fixed

The first integration run passed uppercase domain enum values to a lowercase
policy corpus. Metadata filtering correctly failed closed, leaving only an
unrestricted coupon document and blocking all 21 sensitive scenarios. The
shared applicability boundary now compares business type, state and city with
case normalization, and both retrieval and Evidence Verifier use that single
implementation. The failed run is not reported as model quality.

## Verification

- Sealed data SHA-256:
  `3ed5480c7d52fcbc2216cc238d2aeab41fa74d76a54ca1f74301715579c92096`
- Sealed report SHA-256:
  `4b66252248ca428b0bda3876451a61e59fdc3adc332a3ee2e24e4f58818866f9`
- Transaction report SHA-256:
  `e9f03e554fcff6c84f17185596aefccc707018bba7360a212bc8ff6dc5ff0cea`
- Manifest: `experiments/manifests/phase6_sealed_and_transactional.json`

## Limitations

- The sealed set is newly authored inside this project, not an external blind
  benchmark.
- The corpus contains only sixteen policy sections.
- The deterministic rule baseline is saturated, so downstream benefit is a
  safety-boundary result rather than a success-rate improvement.
- Production serving, cache invalidation and larger-corpus ANN behavior remain
  outside Phase 6 acceptance.
