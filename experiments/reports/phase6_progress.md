# Phase 6 retrieval and evidence-verification progress

Date: 2026-08-08  
Status: Phase 6A complete; Phase 6 selection gate remains open

## Delivered

- Frozen 10-section policy corpus with stable evidence IDs and version,
  effective-time, business-type, order-state and city metadata.
- Frozen 12-query development set written before measured retrieval results.
- Expired-version, similar-coupon, wrong-city and wrong-business-type Hard
  Negatives.
- Dependency-free Chinese/English BM25 baseline.
- Optional metadata filtering at retrieval time.
- Recall@K, MRR, nDCG and citation-accuracy metrics.
- Deterministic Evidence Verifier checking existence, metadata applicability,
  expiry and required-evidence sufficiency.

## Why BM25 first

The environment has no cached embedding model or installed dense-retrieval
stack. BM25 provides the smallest inspectable baseline and isolates corpus,
metadata and metric errors before model variance. The cached Qwen models are
generation models and are not relabeled as embedding models.

## Initial results

| Variant | Recall@3 | MRR | nDCG@3 | Citation accuracy@3 | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 only | 1.0000 | 0.9583 | 0.9692 | 0.3333 | 0.2353 ms |
| BM25 + metadata | 1.0000 | 1.0000 | 1.0000 | 0.3333 | 0.1187 ms |

Metadata removes the expired 2025.4 policy and wrong-city/business candidates,
fixing the only rank-one error in this set. Latency differences at this scale
are microbenchmark noise and are not used as a speed claim.

Citation accuracy remains low because returning three candidates yields one
gold citation and two non-gold candidates on average. The deterministic
Evidence Verifier prevents expired/inapplicable sections from being accepted,
but relevance precision still requires a harder dataset and component
comparison.

## Reproduction

```text
PYTHONPATH=src .venv/bin/python scripts/run_phase6_lexical_eval.py \
  --code-revision 11c9587 \
  --output artifacts/reports/phase6_lexical_eval.json
```

- Corpus SHA-256:
  `d7fc54d070a6fc0b2bcf142513a473e2f33044d2d2cad3e7ee47e02960160128`
- Query SHA-256:
  `d95e05513bdad1c90b5d4c2f0ea0eaaf5c584e8e66a422a49681c29f4965066e`
- Report SHA-256:
  `58b92c8d8f5b2b9e804321472c485f83bd301e70659298c093b1974c7ef0680c`
- Manifest: `experiments/manifests/phase6_lexical_eval.json`

## Open work

- Expand and freeze a harder development/test set with paraphrases,
  multi-evidence answers and closer active-policy Hard Negatives.
- Add query rewrite and multi-query retrieval ablations.
- Select an embedding model only after candidate license/offline/runtime gates.
- Compare lexical-only, dense-only, hybrid and hybrid+reranker under identical
  retrieval and latency budgets.
- Measure citation verification and end-to-end Agent benefit.

Dense and reranker metrics remain `TBD`; Phase 6 is not accepted yet.
