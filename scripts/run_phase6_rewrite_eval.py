#!/usr/bin/env python3
"""Evaluate harder Phase 6 lexical, rewrite and multi-query variants."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from servicepilot.retrieval import (
    BM25PolicyRetriever,
    DeterministicQueryRewriter,
    MultiQueryRRFRetriever,
    evaluate_retrieval,
    load_policy_corpus,
    load_retrieval_queries,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/reports/phase6_rewrite_eval.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    corpus_paths = (
        Path("data/policies/phase6_corpus.jsonl"),
        Path("data/policies/phase6_hard_negatives.jsonl"),
    )
    query_paths = (
        Path("data/eval/phase6_retrieval_queries.jsonl"),
        Path("data/eval/phase6_retrieval_queries_hard.jsonl"),
    )
    corpus = tuple(
        item for path in corpus_paths for item in load_policy_corpus(path)
    )
    queries = tuple(
        item for path in query_paths for item in load_retrieval_queries(path)
    )
    now = datetime(2026, 8, 8, tzinfo=UTC)
    lexical = BM25PolicyRetriever(corpus)
    multi_query = MultiQueryRRFRetriever(lexical)
    variants: dict[str, object] = {}
    all_results: dict[str, object] = {}
    for name in ("bm25_metadata", "bm25_rewrite_rrf"):
        started = perf_counter()
        if name == "bm25_metadata":
            results = {
                query.query_id: lexical.search(
                    query, now=now, top_k=args.top_k, metadata_filter=True
                )
                for query in queries
            }
        else:
            results = {
                query.query_id: multi_query.search(
                    query, now=now, top_k=args.top_k
                )
                for query in queries
            }
        elapsed = perf_counter() - started
        variants[name] = {
            "metrics_at_3": evaluate_retrieval(
                queries, results, top_k=args.top_k
            ).model_dump(mode="json"),
            "metrics_at_1": evaluate_retrieval(
                queries, results, top_k=1
            ).model_dump(mode="json"),
            "mean_latency_ms": round(elapsed * 1000 / len(queries), 4),
        }
        all_results[name] = {
            query_id: [item.model_dump(mode="json") for item in hits]
            for query_id, hits in results.items()
        }
    rewriter = DeterministicQueryRewriter()
    payload = {
        "code_revision": args.code_revision,
        "corpus_count": len(corpus),
        "query_count": len(queries),
        "top_k": args.top_k,
        "corpus_files": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in corpus_paths
        },
        "query_files": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in query_paths
        },
        "mean_query_variants": round(
            sum(len(rewriter.rewrite(query)) for query in queries) / len(queries),
            4,
        ),
        "variants": variants,
        "results": all_results,
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
