#!/usr/bin/env python3
"""Benchmark M3 dense retrieval with and without a cross-encoder reranker."""

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from servicepilot.retrieval import (
    EvidenceVerifier,
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
    parser.add_argument("--reranker-id", required=True)
    parser.add_argument("--reranker-revision", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--device", choices=("cuda",), default="cuda")
    parser.add_argument("--dtype", choices=("float16", "bfloat16"), default="float16")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--candidate-k", type=int, default=6)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def snapshot_size(path: Path) -> int:
    excluded_roots = {"onnx", "imgs"}
    return sum(
        item.stat().st_size
        for item in path.rglob("*")
        if item.is_file() and item.relative_to(path).parts[0] not in excluded_roots
    )


def main() -> None:
    args = parse_args()
    if args.candidate_k < args.top_k or min(args.top_k, args.repetitions) <= 0:
        raise SystemExit("candidate-k must be >= positive top-k; repetitions must be positive")
    import torch
    import torch.nn.functional as functional
    from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

    if not torch.cuda.is_available():
        raise SystemExit("CUDA requested but unavailable")
    dtype = {"float16": torch.float16, "bfloat16": torch.bfloat16}[args.dtype]
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.cuda.reset_peak_memory_stats()
    corpus_paths = (
        Path("data/policies/phase6_corpus.jsonl"),
        Path("data/policies/phase6_hard_negatives.jsonl"),
    )
    query_paths = (
        Path("data/eval/phase6_retrieval_queries.jsonl"),
        Path("data/eval/phase6_retrieval_queries_hard.jsonl"),
    )
    corpus = tuple(item for path in corpus_paths for item in load_policy_corpus(path))
    queries = tuple(item for path in query_paths for item in load_retrieval_queries(path))
    now = datetime(2026, 8, 8, tzinfo=UTC)

    print("loading BAAI/bge-m3 dense retriever", file=sys.stderr, flush=True)
    load_started = perf_counter()
    dense_tokenizer = AutoTokenizer.from_pretrained(args.embedding_path, local_files_only=True)
    dense_model = AutoModel.from_pretrained(
        args.embedding_path, local_files_only=True, torch_dtype=dtype
    ).to(args.device)
    dense_model.eval()
    torch.cuda.synchronize()
    dense_load_seconds = perf_counter() - load_started

    def dense_encode(texts: list[str]) -> Any:
        batches: list[Any] = []
        for start in range(0, len(texts), args.batch_size):
            encoded = dense_tokenizer(
                texts[start : start + args.batch_size],
                padding=True,
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            inputs = {key: value.to(args.device) for key, value in encoded.items()}
            with torch.inference_mode():
                output = dense_model(**inputs).last_hidden_state[:, 0]
                output = functional.normalize(output.float(), p=2, dim=1)
            batches.append(output.cpu())
        return torch.cat(batches, dim=0)

    corpus_embeddings = dense_encode([document.text for document in corpus])
    dense_encode([queries[0].text])
    dense_latencies: list[float] = []
    query_embeddings = None
    for _ in range(args.repetitions):
        torch.cuda.synchronize()
        started = perf_counter()
        query_embeddings = dense_encode([query.text for query in queries])
        torch.cuda.synchronize()
        dense_latencies.append((perf_counter() - started) * 1000)
    assert query_embeddings is not None
    similarities = query_embeddings @ corpus_embeddings.T
    dense_candidates: dict[str, tuple[SearchHit, ...]] = {}
    for query_index, query in enumerate(queries):
        scored = [
            (float(similarities[query_index, index]), document)
            for index, document in enumerate(corpus)
            if is_applicable(document, query, now)
        ]
        scored.sort(key=lambda item: (-item[0], item[1].evidence_id))
        dense_candidates[query.query_id] = tuple(
            SearchHit(
                evidence_id=document.evidence_id,
                score=round(score, 8),
                rank=rank,
                text=document.text,
            )
            for rank, (score, document) in enumerate(scored[: args.candidate_k], start=1)
        )

    print(f"loading {args.reranker_id}", file=sys.stderr, flush=True)
    load_started = perf_counter()
    rerank_tokenizer = AutoTokenizer.from_pretrained(args.reranker_path, local_files_only=True)
    rerank_model = AutoModelForSequenceClassification.from_pretrained(
        args.reranker_path, local_files_only=True, torch_dtype=dtype
    ).to(args.device)
    rerank_model.eval()
    torch.cuda.synchronize()
    reranker_load_seconds = perf_counter() - load_started

    pairs = [
        (query.text, hit.text) for query in queries for hit in dense_candidates[query.query_id]
    ]

    def score_pairs() -> list[float]:
        scores: list[float] = []
        for start in range(0, len(pairs), args.batch_size):
            batch = pairs[start : start + args.batch_size]
            encoded = rerank_tokenizer(
                [item[0] for item in batch],
                [item[1] for item in batch],
                padding=True,
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            inputs = {key: value.to(args.device) for key, value in encoded.items()}
            with torch.inference_mode():
                logits = rerank_model(**inputs).logits.reshape(-1)
            scores.extend(logits.float().cpu().tolist())
        return scores

    score_pairs()
    reranker_latencies: list[float] = []
    reranker_scores: list[float] = []
    for _ in range(args.repetitions):
        torch.cuda.synchronize()
        started = perf_counter()
        reranker_scores = score_pairs()
        torch.cuda.synchronize()
        reranker_latencies.append((perf_counter() - started) * 1000)

    reranked: dict[str, tuple[SearchHit, ...]] = {}
    offset = 0
    for query in queries:
        candidates = dense_candidates[query.query_id]
        scores = reranker_scores[offset : offset + len(candidates)]
        offset += len(candidates)
        reranked[query.query_id] = rank_by_cross_encoder(candidates, scores, top_k=args.top_k)
    dense_results = {
        query.query_id: dense_candidates[query.query_id][: args.top_k] for query in queries
    }
    variants = {"m3_dense": dense_results, "m3_dense_reranker": reranked}
    verifier = EvidenceVerifier(corpus)

    def agent_metrics(results: dict[str, tuple[SearchHit, ...]]) -> dict[str, Any]:
        single = [query for query in queries if len(query.gold_evidence_ids) == 1]
        top1_success = sum(
            verifier.verify(
                query,
                (results[query.query_id][0].evidence_id,),
                required_evidence_ids=query.gold_evidence_ids,
                now=now,
            ).sufficient
            for query in single
        )
        top3_success = sum(
            verifier.verify(
                query,
                tuple(hit.evidence_id for hit in results[query.query_id]),
                required_evidence_ids=query.gold_evidence_ids,
                now=now,
            ).sufficient
            for query in queries
        )
        return {
            "single_evidence_top1_success_rate": round(top1_success / len(single), 4),
            "all_query_top3_success_rate": round(top3_success / len(queries), 4),
            "single_evidence_task_count": len(single),
            "all_query_task_count": len(queries),
        }

    payload = {
        "experiment": "phase6_m3_reranker_pipeline",
        "code_revision": args.code_revision,
        "embedding": {
            "model_id": "BAAI/bge-m3",
            "revision": args.embedding_revision,
            "snapshot_bytes": snapshot_size(args.embedding_path),
        },
        "reranker": {
            "model_id": args.reranker_id,
            "revision": args.reranker_revision,
            "snapshot_bytes": snapshot_size(args.reranker_path),
        },
        "runtime": {
            "device": args.device,
            "dtype": args.dtype,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "gpu_name": torch.cuda.get_device_name(0),
            "torch_version": torch.__version__,
            "transformers_version": __import__("transformers").__version__,
            "dense_load_seconds": round(dense_load_seconds, 4),
            "reranker_load_seconds": round(reranker_load_seconds, 4),
            "dense_query_batch_ms": [round(item, 4) for item in dense_latencies],
            "reranker_query_batch_ms": [round(item, 4) for item in reranker_latencies],
            "mean_dense_ms_per_query": round(
                sum(dense_latencies) / len(dense_latencies) / len(queries), 4
            ),
            "mean_reranker_ms_per_query": round(
                sum(reranker_latencies) / len(reranker_latencies) / len(queries), 4
            ),
            "mean_pipeline_ms_per_query": round(
                (sum(dense_latencies) + sum(reranker_latencies))
                / len(dense_latencies)
                / len(queries),
                4,
            ),
            "peak_allocated_vram_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
            "peak_reserved_vram_mib": round(torch.cuda.max_memory_reserved() / 1024**2, 2),
        },
        "corpus_count": len(corpus),
        "query_count": len(queries),
        "candidate_k": args.candidate_k,
        "top_k": args.top_k,
        "data_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (*corpus_paths, *query_paths)
        },
        "variants": {
            name: {
                "metrics_at_3": evaluate_retrieval(queries, results, top_k=args.top_k).model_dump(
                    mode="json"
                ),
                "metrics_at_1": evaluate_retrieval(queries, results, top_k=1).model_dump(
                    mode="json"
                ),
                "evidence_agent": agent_metrics(results),
                "results": {
                    query_id: [hit.model_dump(mode="json") for hit in hits]
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
