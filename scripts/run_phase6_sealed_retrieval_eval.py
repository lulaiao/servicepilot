#!/usr/bin/env python3
"""Evaluate exactly the two frozen Phase 6 sealed retrieval candidates."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from servicepilot.retrieval import (
    SearchHit,
    evaluate_retrieval,
    load_policy_corpus,
    load_retrieval_queries,
    rank_by_cross_encoder,
)
from servicepilot.retrieval.lexical import is_applicable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-path", type=Path, required=True)
    parser.add_argument("--embedding-revision", required=True)
    parser.add_argument("--reranker-path", type=Path, required=True)
    parser.add_argument("--reranker-revision", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--device", choices=("cuda",), default="cuda")
    parser.add_argument("--dtype", choices=("float16", "bfloat16"), default="float16")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def normalize(values: list[float]) -> list[float]:
    low, high = min(values), max(values)
    if low == high:
        return [0.0] * len(values)
    return [(value - low) / (high - low) for value in values]


def evidence_metrics(
    queries: tuple[Any, ...], results: dict[str, tuple[SearchHit, ...]]
) -> dict[str, Any]:
    required_top1 = 0
    complete_top3 = 0
    contradictory_top1 = 0
    failures: list[dict[str, Any]] = []
    for query in queries:
        returned = tuple(hit.evidence_id for hit in results[query.query_id])
        required = set(query.required_evidence_ids)
        top1_ok = returned[0] in required
        complete = required <= set(returned[:3])
        contradictory = returned[0] in set(query.contradictory_evidence_ids)
        required_top1 += top1_ok
        complete_top3 += complete
        contradictory_top1 += contradictory
        if not top1_ok or not complete or contradictory:
            failures.append(
                {
                    "query_id": query.query_id,
                    "required": sorted(required),
                    "returned": returned,
                    "top1_ok": top1_ok,
                    "complete_at_3": complete,
                    "contradictory_top1": contradictory,
                }
            )
    count = len(queries)
    return {
        "required_top1_accuracy": round(required_top1 / count, 4),
        "required_complete_at_3": round(complete_top3 / count, 4),
        "contradictory_top1_rate": round(contradictory_top1 / count, 4),
        "failures": failures,
    }


def main() -> None:
    args = parse_args()
    import torch
    import torch.nn.functional as functional
    from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

    if not torch.cuda.is_available():
        raise SystemExit("CUDA requested but unavailable")
    if args.repetitions <= 0:
        raise SystemExit("repetitions must be positive")
    dtype = {"float16": torch.float16, "bfloat16": torch.bfloat16}[args.dtype]
    torch.manual_seed(20260808)
    torch.cuda.manual_seed_all(20260808)
    torch.cuda.reset_peak_memory_stats()
    corpus_paths = (
        Path("data/policies/phase6_corpus.jsonl"),
        Path("data/policies/phase6_hard_negatives.jsonl"),
    )
    sealed_path = Path("data/eval/phase6_retrieval_sealed.jsonl")
    corpus = tuple(item for path in corpus_paths for item in load_policy_corpus(path))
    queries = load_retrieval_queries(sealed_path)
    now = datetime(2026, 8, 8, tzinfo=UTC)

    dense_tokenizer = AutoTokenizer.from_pretrained(args.embedding_path, local_files_only=True)
    dense_model = AutoModel.from_pretrained(
        args.embedding_path, local_files_only=True, torch_dtype=dtype
    ).to(args.device)
    rerank_tokenizer = AutoTokenizer.from_pretrained(args.reranker_path, local_files_only=True)
    rerank_model = AutoModelForSequenceClassification.from_pretrained(
        args.reranker_path, local_files_only=True, torch_dtype=dtype
    ).to(args.device)
    dense_model.eval()
    rerank_model.eval()

    def dense_encode(texts: list[str]) -> Any:
        encoded = dense_tokenizer(
            texts, padding=True, truncation=True, max_length=512, return_tensors="pt"
        )
        inputs = {key: value.to(args.device) for key, value in encoded.items()}
        with torch.inference_mode():
            output = dense_model(**inputs).last_hidden_state[:, 0]
        return functional.normalize(output.float(), p=2, dim=1).cpu()

    corpus_embeddings = dense_encode([document.text for document in corpus])
    query_embeddings = dense_encode([query.text for query in queries])
    similarities = query_embeddings @ corpus_embeddings.T
    candidates: dict[str, tuple[SearchHit, ...]] = {}
    for query_index, query in enumerate(queries):
        scored = [
            (float(similarities[query_index, index]), document)
            for index, document in enumerate(corpus)
            if is_applicable(document, query, now)
        ]
        scored.sort(key=lambda item: (-item[0], item[1].evidence_id))
        candidates[query.query_id] = tuple(
            SearchHit(evidence_id=document.evidence_id, score=score, rank=rank, text=document.text)
            for rank, (score, document) in enumerate(scored[:6], start=1)
        )
    pairs = [(query.text, hit.text) for query in queries for hit in candidates[query.query_id]]

    def rerank_scores() -> list[float]:
        scores: list[float] = []
        for start in range(0, len(pairs), 16):
            batch = pairs[start : start + 16]
            encoded = rerank_tokenizer(
                [item[0] for item in batch],
                [item[1] for item in batch],
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            inputs = {key: value.to(args.device) for key, value in encoded.items()}
            with torch.inference_mode():
                scores.extend(rerank_model(**inputs).logits.reshape(-1).float().cpu().tolist())
        return scores

    rerank_scores()
    latencies: list[float] = []
    scores: list[float] = []
    for _ in range(args.repetitions):
        torch.cuda.synchronize()
        started = perf_counter()
        scores = rerank_scores()
        torch.cuda.synchronize()
        latencies.append((perf_counter() - started) * 1000)
    dense_results = {query.query_id: candidates[query.query_id][:3] for query in queries}
    fusion_results: dict[str, tuple[SearchHit, ...]] = {}
    offset = 0
    for query in queries:
        current = candidates[query.query_id]
        current_scores = scores[offset : offset + len(current)]
        offset += len(current)
        dense_normalized = normalize([hit.score for hit in current])
        rerank_normalized = normalize(current_scores)
        fused = [
            0.5 * dense_score + 0.5 * rerank_score
            for dense_score, rerank_score in zip(dense_normalized, rerank_normalized, strict=True)
        ]
        fusion_results[query.query_id] = rank_by_cross_encoder(current, fused, top_k=3)
    variants = {"m3_dense_only": dense_results, "plain_k6_fusion_050_050": fusion_results}
    payload = {
        "experiment": "phase6_sealed_retrieval",
        "code_revision": args.code_revision,
        "sealed_sha256": hashlib.sha256(sealed_path.read_bytes()).hexdigest(),
        "query_count": len(queries),
        "locked_configuration": {
            "candidate_k": 6,
            "dense_weight": 0.5,
            "reranker_weight": 0.5,
            "query_input": "plain",
        },
        "model_revisions": {
            "embedding": args.embedding_revision,
            "reranker": args.reranker_revision,
        },
        "runtime": {
            "reranker_batch_latency_ms": [round(item, 4) for item in latencies],
            "mean_reranker_ms_per_query": round(sum(latencies) / len(latencies) / len(queries), 4),
            "peak_allocated_vram_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
        },
        "variants": {
            name: {
                "retrieval": evaluate_retrieval(queries, results, top_k=3).model_dump(mode="json"),
                "evidence": evidence_metrics(queries, results),
                "results": {
                    query_id: [hit.evidence_id for hit in hits]
                    for query_id, hits in results.items()
                },
            }
            for name, results in variants.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
