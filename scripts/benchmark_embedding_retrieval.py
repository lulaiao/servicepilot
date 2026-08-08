#!/usr/bin/env python3
"""Offline CUDA benchmark for dense-only, BM25 and hybrid retrieval."""

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
    BM25PolicyRetriever,
    SearchHit,
    evaluate_retrieval,
    load_policy_corpus,
    load_retrieval_queries,
    reciprocal_rank_fusion,
)
from servicepilot.retrieval.lexical import is_applicable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--query-prefix", default="")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument(
        "--dtype", choices=("float32", "float16", "bfloat16"), default="float16"
    )
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260808)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def main() -> None:
    args = parse_args()
    if args.repetitions <= 0 or args.batch_size <= 0 or args.max_length <= 0:
        raise SystemExit("repetitions, batch-size and max-length must be positive")
    if not args.model_path.is_dir():
        raise SystemExit(f"model path does not exist: {args.model_path}")
    import torch
    import torch.nn.functional as functional
    from transformers import AutoModel, AutoTokenizer

    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA requested but unavailable")
    dtype = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }[args.dtype]
    torch.manual_seed(args.seed)
    if args.device == "cuda":
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
    print(f"loading {args.model_id} on {args.device}", file=sys.stderr, flush=True)
    load_started = perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(args.model_path, local_files_only=True)
    model = AutoModel.from_pretrained(
        args.model_path, local_files_only=True, torch_dtype=dtype
    ).to(args.device)
    model.eval()
    if args.device == "cuda":
        torch.cuda.synchronize()
    load_seconds = perf_counter() - load_started

    def encode(texts: list[str]) -> Any:
        batches: list[Any] = []
        for start in range(0, len(texts), args.batch_size):
            encoded = tokenizer(
                texts[start : start + args.batch_size],
                padding=True,
                truncation=True,
                max_length=args.max_length,
                return_tensors="pt",
            )
            inputs = {key: value.to(args.device) for key, value in encoded.items()}
            with torch.inference_mode():
                output = model(**inputs).last_hidden_state[:, 0]
                output = functional.normalize(output.float(), p=2, dim=1)
            batches.append(output.cpu())
        return torch.cat(batches, dim=0)

    corpus_started = perf_counter()
    corpus_embeddings = encode([item.text for item in corpus])
    if args.device == "cuda":
        torch.cuda.synchronize()
    corpus_encode_ms = (perf_counter() - corpus_started) * 1000
    query_texts = [f"{args.query_prefix}{item.text}" for item in queries]
    encode(query_texts[: min(2, len(query_texts))])
    query_latencies: list[float] = []
    query_embeddings = None
    for _ in range(args.repetitions):
        if args.device == "cuda":
            torch.cuda.synchronize()
        started = perf_counter()
        query_embeddings = encode(query_texts)
        if args.device == "cuda":
            torch.cuda.synchronize()
        query_latencies.append((perf_counter() - started) * 1000)
    assert query_embeddings is not None
    similarities = query_embeddings @ corpus_embeddings.T
    now = datetime(2026, 8, 8, tzinfo=UTC)
    dense_results: dict[str, tuple[SearchHit, ...]] = {}
    lexical = BM25PolicyRetriever(corpus)
    lexical_results: dict[str, tuple[SearchHit, ...]] = {}
    hybrid_results: dict[str, tuple[SearchHit, ...]] = {}
    for query_index, query in enumerate(queries):
        scored = [
            (float(similarities[query_index, index]), document)
            for index, document in enumerate(corpus)
            if is_applicable(document, query, now)
        ]
        scored.sort(key=lambda item: (-item[0], item[1].evidence_id))
        dense = tuple(
            SearchHit(
                evidence_id=document.evidence_id,
                score=round(score, 8),
                rank=rank,
                text=document.text,
            )
            for rank, (score, document) in enumerate(scored[:6], start=1)
        )
        bm25 = lexical.search(query, now=now, top_k=6, metadata_filter=True)
        dense_results[query.query_id] = dense[: args.top_k]
        lexical_results[query.query_id] = bm25[: args.top_k]
        hybrid_results[query.query_id] = reciprocal_rank_fusion(
            (bm25, dense), top_k=args.top_k
        )
    result_sets = {
        "bm25_metadata": lexical_results,
        "dense_only": dense_results,
        "hybrid_rrf": hybrid_results,
    }
    variants = {
        name: {
            "metrics_at_3": evaluate_retrieval(
                queries, results, top_k=args.top_k
            ).model_dump(mode="json"),
            "metrics_at_1": evaluate_retrieval(
                queries, results, top_k=1
            ).model_dump(mode="json"),
        }
        for name, results in result_sets.items()
    }
    payload = {
        "candidate": {
            "model_id": args.model_id,
            "path": str(args.model_path),
            "revision": args.revision,
            "query_prefix": args.query_prefix,
            "device": args.device,
            "dtype": args.dtype,
            "max_length": args.max_length,
            "batch_size": args.batch_size,
            "model_disk_bytes": directory_size(args.model_path),
        },
        "runtime": {
            "torch_version": torch.__version__,
            "transformers_version": __import__("transformers").__version__,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "gpu_name": (
                torch.cuda.get_device_name(0) if args.device == "cuda" else None
            ),
            "model_load_seconds": round(load_seconds, 4),
            "corpus_encode_ms": round(corpus_encode_ms, 4),
            "query_encode_ms": [round(item, 4) for item in query_latencies],
            "mean_query_encode_ms": round(
                sum(query_latencies) / len(query_latencies), 4
            ),
            "mean_query_encode_ms_per_query": round(
                sum(query_latencies) / len(query_latencies) / len(queries), 4
            ),
            "peak_allocated_vram_mib": (
                round(torch.cuda.max_memory_allocated() / 1024**2, 2)
                if args.device == "cuda"
                else None
            ),
            "peak_reserved_vram_mib": (
                round(torch.cuda.max_memory_reserved() / 1024**2, 2)
                if args.device == "cuda"
                else None
            ),
        },
        "corpus_count": len(corpus),
        "query_count": len(queries),
        "top_k": args.top_k,
        "data_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (*corpus_paths, *query_paths)
        },
        "variants": variants,
        "results": {
            name: {
                query_id: [item.model_dump(mode="json") for item in hits]
                for query_id, hits in results.items()
            }
            for name, results in result_sets.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
