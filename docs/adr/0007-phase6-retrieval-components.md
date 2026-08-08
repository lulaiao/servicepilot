# ADR 0007: Select Phase 6 retrieval components by downstream evidence quality

- Status: Accepted
- Date: 2026-08-08

## Context

ServicePilot must retrieve exact policy evidence under version, business type,
order state, city and effective-time constraints. Phase 6A began without a
cached embedding model, Sentence Transformers, FAISS or BM25 dependency.
Using cached Qwen generation models as embedding models would not be a valid
dense-retrieval comparison. Phase 6C therefore adds two purpose-built,
MIT-licensed BGE embedding candidates at pinned revisions.

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

Phase 6B expands to 16 documents and 24 queries, including six multi-evidence
questions. BM25+metadata Recall@1 falls to 0.7083. Deterministic rewrite+RRF
does not improve Recall, MRR or citation accuracy and approximately doubles
latency, so it is rejected for the mainline. The remaining rank-one gap now
provides a measurable target for dense/hybrid candidates.

## Embedding decision

Advance `BAAI/bge-m3` dense-only to the reranker and end-to-end evaluation
gate. Retain BM25 with metadata filtering as the dependency-light CPU fallback.
Do not add hybrid RRF to the M3 mainline at this gate because its results are
identical to M3 dense-only. Do not select BGE-small-zh-v1.5: although its hybrid
variant modestly improves BM25, its dense-only result does not.

On the frozen 16-document/24-query development set, M3 dense improves
Recall@1 from 0.7083 to 0.8333 and MRR@3 from 0.9167 to 0.9792 versus BM25.
The cost is material: 2.30 GB versus 192 MB of Transformers snapshot files,
1.3961 versus 0.4498 ms/query embedding latency, and 1,107.03 versus 63.95 MiB
peak allocated VRAM compared with BGE-small. The quality gain is accepted for
the next research gate, not yet as a production deployment decision.

## Reranker decision

Reject both `BAAI/bge-reranker-base` and `BAAI/bge-reranker-v2-m3` for the
mainline. With M3 dense top-six candidates fixed, both preserve Recall@3=1.0
but reduce MRR@3, nDCG@3, rank-one citation accuracy and Policy Evidence Agent
success. They also add 5.4638 and 8.7302 ms/query respectively. This is a
measured negative result: adding a cross-encoder is not treated as an
architectural improvement when downstream evidence quality declines.

Keep M3 dense-only with metadata filtering as the selected pipeline for the
transactional-Agent integration gate. Reconsider reranking only if a larger
sealed set demonstrates a quality gain under a declared latency budget.

Phase 6E refines, but does not yet reverse, that decision. On a correlated
120-query diagnostic set, full reranking remains harmful while plain-query
top-six 0.5/0.5 normalized score fusion improves required top-one accuracy
from 0.8917 to 0.9333 and restores q02, q10 and q15. Top-ten yields no extra
quality and metadata/instruction enrichment substantially degrades results.

Consequently, M3 dense-only stays on the mainline. Plain top-six fixed-weight
fusion is the only reranker configuration admitted to the sealed-test gate.
The reranker must remain a secondary signal and may not fully replace dense
ordering without new evidence.

## Final decision

The frozen 36-query sealed gate selects plain-query top-six fixed 0.5/0.5
normalized score fusion over dense-only: MRR@3 is 0.9861 versus 0.9722 and
required top-one accuracy is 0.9722 versus 0.9444, with equal Recall@3 and no
contradictory rank-one results.

Adopt this fusion pipeline for the GPU policy path and keep metadata-filtered
BM25 as the CPU fallback. Transactional actions fail closed when required
evidence is incomplete. On the existing 36 business scenarios, the gate
preserves 100% task success and adds a tested no-write boundary for missing
evidence. Metadata comparison is case-normalized at the shared retrieval and
verification boundary.

## Acceptance condition

The acceptance condition is met by the frozen sealed comparison and the
transactional Harness/Judge integration. This is a project-level component
decision, not a claim of production generalization beyond the documented
sixteen-section corpus and internally authored sealed set.
