#!/usr/bin/env python3
"""Evaluate Phase 6 dependency-free lexical retrieval baselines."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from servicepilot.retrieval import (
    BM25PolicyRetriever,
    evaluate_retrieval,
    load_policy_corpus,
    load_retrieval_queries,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument(
        "--corpus", type=Path, default=Path("data/policies/phase6_corpus.jsonl")
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path("data/eval/phase6_retrieval_queries.jsonl"),
    )
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/phase6_lexical_eval.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    corpus = load_policy_corpus(args.corpus)
    queries = load_retrieval_queries(args.queries)
    retriever = BM25PolicyRetriever(corpus)
    now = datetime(2026, 8, 8, tzinfo=UTC)
    variants: dict[str, object] = {}
    raw_results: dict[str, dict[str, list[dict[str, object]]]] = {}
    for name, metadata_filter in (
        ("bm25_only", False),
        ("bm25_metadata", True),
    ):
        started = perf_counter()
        results = {
            query.query_id: retriever.search(
                query,
                now=now,
                top_k=args.top_k,
                metadata_filter=metadata_filter,
            )
            for query in queries
        }
        elapsed = perf_counter() - started
        variants[name] = {
            "metrics": evaluate_retrieval(
                queries, results, top_k=args.top_k
            ).model_dump(mode="json"),
            "total_latency_ms": round(elapsed * 1000, 4),
            "mean_latency_ms": round(elapsed * 1000 / len(queries), 4),
        }
        raw_results[name] = {
            query_id: [item.model_dump(mode="json") for item in hits]
            for query_id, hits in results.items()
        }
    payload = {
        "code_revision": args.code_revision,
        "corpus_count": len(corpus),
        "query_count": len(queries),
        "top_k": args.top_k,
        "corpus_sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest(),
        "query_sha256": hashlib.sha256(args.queries.read_bytes()).hexdigest(),
        "variants": variants,
        "results": raw_results,
        "dense_model": "TBD",
        "reranker_model": "TBD",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
