# ADR 0007: Select Phase 6 retrieval components by downstream evidence quality

- Status: Proposed
- Date: 2026-08-08

## Context

ServicePilot must retrieve exact policy evidence under version, business type,
order state, city and effective-time constraints. The current environment has
no cached embedding model, Sentence Transformers, FAISS or BM25 dependency.
Using the cached Qwen generation models as embedding models would not be a
valid dense-retrieval comparison.

## Provisional decision

Start with a dependency-free BM25 implementation as the minimum lexical
baseline. Freeze the corpus, query set, metadata and gold evidence before
evaluating learned components. Keep dense and reranker choices `TBD`.

A dense model must pass license, fixed-revision, offline execution, language
fit, context length and CUDA/PyTorch compatibility gates. It must then improve
Recall@K or end-to-end evidence success under the same corpus, queries and
latency budget. A reranker must improve MRR/nDCG or citation precision enough
to justify added latency and memory.

## Initial evidence

The 10-document/12-query Phase 6A dataset contains expired-policy, similar
coupon, wrong-city and wrong-business-type Hard Negatives. BM25+metadata reaches
Recall@3, MRR and nDCG of 1.0 at approximately 0.119 ms/query, but citation
accuracy@3 is only 0.3333. The set is therefore useful for metadata safety but
too small/easy to justify a dense model.

## Acceptance condition

This ADR remains Proposed until a harder frozen set supports an equal-budget
lexical-only, dense-only, hybrid and hybrid+reranker comparison, including
Recall@K, MRR/nDCG, citation accuracy, latency and downstream evidence benefit.
