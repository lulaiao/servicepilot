# Phase 6 retrieval and evidence-verification progress

Date: 2026-08-08  
Status: Phase 6A–F complete; Phase 6 accepted

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

## Phase 6B harder set and query-rewrite ablation

The extension freezes six additional active-policy Hard Negatives and twelve
queries, including six multi-evidence questions and colloquial paraphrases.
The combined development set contains 16 documents and 24 queries.

| Variant | Recall@3 | MRR | nDCG@3 | Citation accuracy@3 | Recall@1 | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 + metadata | 1.0000 | 0.9167 | 0.9318 | 0.4167 | 0.7083 | 0.1717 ms |
| Rewrite + BM25 + RRF | 1.0000 | 0.9167 | 0.9351 | 0.4167 | 0.7083 | 0.3564 ms |

The harder set creates a real rank-one gap. Deterministic rewrite plus RRF does
not improve Recall, MRR, citation accuracy or Recall@1. Its small nDCG gain
comes with roughly twice the mean latency, so it is rejected for the mainline.
This negative result prevents more calls from being mislabeled as progress.

```text
PYTHONPATH=src .venv/bin/python scripts/run_phase6_rewrite_eval.py \
  --code-revision 341f4bf \
  --output artifacts/reports/phase6_rewrite_eval.json
```

- Hard corpus SHA-256:
  `6c21e4c32392449b2a6bb8a5cc1770c5ab708e139d28d143e5c208e8f4ed041c`
- Hard query SHA-256:
  `0b70aacea267265b5c9ca364b7348981bb5f2a9564889ccdfc439228f6b9ef40`
- Report SHA-256:
  `54efbee8459a9988e765a346f69cbf20dcb384bfb2591f726377c74ddcfd2f1d`
- Manifest: `experiments/manifests/phase6_rewrite_eval.json`

The next gate is embedding-model selection and an equal-budget dense/hybrid
comparison. Reranking remains downstream of that result.

## Phase 6C embedding selection

Two MIT-licensed, revision-pinned BGE candidates were run offline with the
same 16-document corpus, 24-query set, FP16 settings and RTX A6000 GPU. BM25,
dense-only and reciprocal-rank-fusion hybrid results use the same metadata
filter and deterministic evaluator.

| Variant | Recall@3 | MRR@3 | nDCG@3 | Recall@1 |
| --- | ---: | ---: | ---: | ---: |
| BM25 + metadata | 1.0000 | 0.9167 | 0.9318 | 0.7083 |
| BGE-small-zh-v1.5 dense | 1.0000 | 0.9097 | 0.9297 | 0.7083 |
| BGE-small-zh-v1.5 hybrid | 1.0000 | 0.9306 | 0.9451 | 0.7500 |
| BGE-M3 dense | 1.0000 | 0.9792 | 0.9813 | 0.8333 |
| BGE-M3 hybrid | 1.0000 | 0.9792 | 0.9813 | 0.8333 |

| Candidate | Snapshot | Query encode / query | Peak allocated VRAM |
| --- | ---: | ---: | ---: |
| BGE-small-zh-v1.5 | 192,250,118 bytes | 0.4498 ms | 63.95 MiB |
| BGE-M3 | 2,295,564,334 bytes | 1.3961 ms | 1,107.03 MiB |

BGE-M3 dense-only advances to the reranker and end-to-end gate. It improves
Recall@1 by 0.1250 and MRR@3 by 0.0625 over BM25. BGE-small is cheaper, but its
dense-only result does not improve BM25; its hybrid gain remains below M3.
Hybrid is not selected for M3 because it produces identical ranking metrics
while adding a second retrieval path. BM25 remains the CPU/offline fallback.

This is a development-set decision, not a production claim. All variants have
Recall@3=1.0 on only 16 documents and 24 queries; sealed-test generalization
and downstream Agent evidence success remain `TBD`.

```text
CUDA_VISIBLE_DEVICES=4 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=src \
  /data/ssd1/lla/conda_envs/mcp-sql-reflex-rl/bin/python \
  scripts/benchmark_embedding_retrieval.py ... \
  --device cuda --dtype float16 --repetitions 3 \
  --code-revision 46f46301287b4567132b2ce14eee1f967df8c658
```

- Small report SHA-256:
  `e15e07dc9301c59ffb2954189033a233f4bfc55122920d27b70b09ffad882210`
- M3 report SHA-256:
  `5b6182127d2abcc1aee7673792dc4ac7f5fadf5f19b60cba98409918904fee30`
- Manifest: `experiments/manifests/phase6_embedding_comparison.json`

The next gate compares the selected dense retriever with a reranker and then
measures whether improved evidence ranking changes deterministic Agent success.

## Phase 6D reranker screening

The reranker receives exactly the top six metadata-applicable M3 dense
candidates and may only reorder them. The final output remains top three. Two
revision-pinned cross-encoders were compared on GPU 4 with FP16: the
Chinese/English `bge-reranker-base` cost point and multilingual
`bge-reranker-v2-m3` quality point.

| Variant | Recall@3 | MRR@3 | nDCG@3 | Citation accuracy@1 | Evidence Agent top-1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| M3 dense | 1.0000 | 0.9792 | 0.9813 | 0.9583 | 0.9444 |
| M3 + reranker-base | 1.0000 | 0.9514 | 0.9538 | 0.9167 | 0.8889 |
| M3 + reranker-v2-m3 | 1.0000 | 0.9583 | 0.9692 | 0.9167 | 0.8889 |

| Pipeline | Dense latency | Added rerank latency | Peak allocated VRAM |
| --- | ---: | ---: | ---: |
| M3 + reranker-base | 1.3120 ms/query | 5.4638 ms/query | 1,648.05 MiB |
| M3 + reranker-v2-m3 | 1.4742 ms/query | 8.7302 ms/query | 2,196.70 MiB |

Both rerankers are rejected for the mainline. Neither changes Recall@3 or the
all-query top-three verifier success of 1.0, while both reduce MRR, nDCG,
rank-one citation accuracy and the Policy Evidence Agent's single-evidence
top-one success. The base model moves q10's gold cancellation section from
rank one to two and q15's coupon-restoration section from rank one to three.
The v2-M3 model moves q02 and q10 cancellation evidence from rank one to two.

The Evidence Agent result is an executable query -> candidate retrieval ->
reranking -> citation -> deterministic Evidence Verifier loop. It is not yet
the transactional Agent loop that performs previews and writes. Therefore the
claim is limited to “no evidence-task benefit”; full business-Agent benefit
remains `TBD` rather than being inferred from retrieval metrics.

- Base report SHA-256:
  `8add2647c0f28ef6c9544470e574bf56c52a14199aa8a527bb7b3aa8dbfec255`
- v2-M3 report SHA-256:
  `c20090c4b8229ffbbe89a800ea4a39afa850e39084d52568bd96a2b39620abf3`
- Manifest: `experiments/manifests/phase6_reranker_comparison.json`

The next gate integrates M3 dense-only into the transactional Agent policy
step and freezes a sealed retrieval/business scenario set. Reranker remains
out of the mainline unless new sealed evidence reverses this result.

## Phase 6E reranker failure diagnostics

A 120-query development diagnostic set adds explicit required, supporting and
contradictory evidence roles across twelve policy families. Combined with the
original 24 queries, the experiment evaluates 144 queries. The set is
template-controlled and improves boundary coverage, but its ten paraphrases
per family are correlated and must not be presented as 120 independent user
samples.

The predeclared matrix compares candidate depths 3/6/10, full replacement,
0.5/0.5 min-max normalized score fusion, a 0.15 probability-margin gate, and
plain versus metadata-enriched reranker input.

| Variant | MRR@3 (144) | nDCG@3 (144) | Required top-1 (120) | Contradictory top-1 |
| --- | ---: | ---: | ---: | ---: |
| M3 dense-only | 0.9491 | 0.9617 | 0.8917 | 0.0083 |
| Plain k6 full rerank | 0.9398 | 0.9555 | 0.8750 | 0.0167 |
| Plain k6 0.5/0.5 fusion | 0.9711 | 0.9780 | 0.9333 | 0.0083 |
| Enriched k10 full rerank | 0.8553 | 0.8894 | 0.7250 | 0.0667 |

Plain k6 fusion restores q02, q10 and q15 and improves both aggregate ranking
and required top-one accuracy over dense-only. Plain k10 fusion produces the
same quality but increases reranker latency from 6.5964 to 7.3669 ms/query, so
k6 dominates k10. Full reranking remains harmful. The enriched prompt is also
rejected: this sequence-classification cross-encoder is not an instruction
model, and adding policy/status/city plus a priority instruction increases
contradictory rank-one errors.

The diagnosis is therefore narrower than “the model is bad”: v2-M3 is useful
as a secondary score but unsafe as the sole ordering authority on this corpus.
The mainline remains M3 dense-only. Plain k6 fixed-weight fusion advances only
as a sealed-test candidate; it is not selected for production from correlated
development templates.

- Diagnostic data SHA-256:
  `a75b9c86e4c3c8c0116182de84786644cadf0dbdcfe4deb7d284bd9dd9d33ccd`
- Raw report SHA-256:
  `15021013a95ffe689bf30e6f293d3d2d15f1c5d55512a8419dc146db61458409`
- Manifest: `experiments/manifests/phase6_reranker_diagnostics.json`
- Label review: `experiments/reports/phase6_evidence_label_review.md`

The next step is a separately authored sealed set followed by transactional
Agent integration comparing dense-only with the single surviving fusion
candidate.

## Phase 6F sealed selection and transactional integration

The sealed set was frozen at commit `cd7f76e` with SHA-256 `3ed5480c...` before
execution. Under the unchanged plain-query k6 0.5/0.5 configuration, fusion
beats dense-only on MRR@3 (0.9861 vs 0.9722), nDCG@3 (0.9807 vs 0.9683) and
required top-one accuracy (0.9722 vs 0.9444), with identical Recall@3=0.9861
and contradictory top-one rate=0.

The fusion winner is integrated as a fail-closed transaction evidence gate.
It obtains complete evidence on all 21 policy-sensitive Phase 3 scenarios and
preserves 36/36 task success, final-state accuracy=1, policy violations=0 and
False-success=0. A missing-evidence regression proves that no write is issued.
The added safety boundary increases average tool calls from 1.556 to 2.139.

An initial integration run exposed uppercase domain statuses versus lowercase
retrieval metadata. The applicability boundary now normalizes casing and is
shared with the Evidence Verifier. Phase 6 is accepted with the limitations in
`experiments/reports/phase6_acceptance.md`.
