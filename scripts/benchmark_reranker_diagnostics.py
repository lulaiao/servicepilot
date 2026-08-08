#!/usr/bin/env python3
"""Run candidate-depth, ranking-strategy and metadata-context diagnostics."""

import argparse
import hashlib
import json
import math
import os
import sys
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
from servicepilot.retrieval.models import RetrievalQuery


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-path", type=Path, required=True)
    parser.add_argument("--embedding-revision", required=True)
    parser.add_argument("--reranker-path", type=Path, required=True)
    parser.add_argument("--reranker-revision", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--device", choices=("cuda",), default="cuda")
    parser.add_argument("--dtype", choices=("float16", "bfloat16"), default="float16")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def enriched_query(query: RetrievalQuery) -> str:
    return (
        "任务：选择直接规定用户问题的主证据；补充规则只有在问题明确询问时才优先。"
        f"政策版本={query.policy_version}；订单状态={query.order_status}；"
        f"城市={query.city}；业务类型={query.business_type}；用户问题={query.text}"
    )


def normalize(values: list[float]) -> list[float]:
    low, high = min(values), max(values)
    if math.isclose(low, high):
        return [0.0] * len(values)
    return [(value - low) / (high - low) for value in values]


def diagnostic_metrics(
    queries: tuple[RetrievalQuery, ...], results: dict[str, tuple[SearchHit, ...]]
) -> dict[str, float | int]:
    top1_required = 0
    top3_complete = 0
    contradictory_top1 = 0
    supporting_top3 = 0
    supporting_queries = 0
    for query in queries:
        returned = tuple(hit.evidence_id for hit in results[query.query_id])
        required = set(query.required_evidence_ids or query.gold_evidence_ids)
        if returned[0] in required:
            top1_required += 1
        if required <= set(returned[:3]):
            top3_complete += 1
        if returned[0] in set(query.contradictory_evidence_ids):
            contradictory_top1 += 1
        if query.supporting_evidence_ids:
            supporting_queries += 1
            if set(returned[:3]) & set(query.supporting_evidence_ids):
                supporting_top3 += 1
    count = len(queries)
    return {
        "query_count": count,
        "required_top1_accuracy": round(top1_required / count, 4),
        "required_complete_at_3": round(top3_complete / count, 4),
        "contradictory_top1_rate": round(contradictory_top1 / count, 4),
        "supporting_recall_at_3": round(supporting_top3 / supporting_queries, 4),
        "supporting_query_count": supporting_queries,
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
    query_paths = (
        Path("data/eval/phase6_retrieval_queries.jsonl"),
        Path("data/eval/phase6_retrieval_queries_hard.jsonl"),
        Path("data/eval/phase6_reranker_diagnostic_queries.jsonl"),
    )
    corpus = tuple(item for path in corpus_paths for item in load_policy_corpus(path))
    queries = tuple(item for path in query_paths for item in load_retrieval_queries(path))
    diagnostic_queries = load_retrieval_queries(query_paths[-1])
    now = datetime(2026, 8, 8, tzinfo=UTC)

    print("loading dense and reranker models", file=sys.stderr, flush=True)
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
        outputs: list[Any] = []
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
                value = dense_model(**inputs).last_hidden_state[:, 0]
                outputs.append(functional.normalize(value.float(), p=2, dim=1).cpu())
        return torch.cat(outputs, dim=0)

    corpus_embeddings = dense_encode([document.text for document in corpus])
    query_embeddings = dense_encode([query.text for query in queries])
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
            SearchHit(evidence_id=document.evidence_id, score=score, rank=rank, text=document.text)
            for rank, (score, document) in enumerate(scored[:10], start=1)
        )

    variants: dict[str, dict[str, tuple[SearchHit, ...]]] = {}
    latency: dict[str, list[float]] = {}
    for context_name, render in (("plain", lambda query: query.text), ("enriched", enriched_query)):
        for candidate_k in (3, 6, 10):
            pairs = [
                (render(query), hit.text)
                for query in queries
                for hit in dense_candidates[query.query_id][:candidate_k]
            ]

            def score_pairs(current_pairs: list[tuple[str, str]]) -> list[float]:
                scores: list[float] = []
                for start in range(0, len(current_pairs), args.batch_size):
                    batch = current_pairs[start : start + args.batch_size]
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
                        scores.extend(
                            rerank_model(**inputs).logits.reshape(-1).float().cpu().tolist()
                        )
                return scores

            score_pairs(pairs)
            times: list[float] = []
            scores: list[float] = []
            for _ in range(args.repetitions):
                torch.cuda.synchronize()
                started = perf_counter()
                scores = score_pairs(pairs)
                torch.cuda.synchronize()
                times.append((perf_counter() - started) * 1000)
            latency[f"{context_name}_k{candidate_k}"] = times
            full_results: dict[str, tuple[SearchHit, ...]] = {}
            fusion_results: dict[str, tuple[SearchHit, ...]] = {}
            gated_results: dict[str, tuple[SearchHit, ...]] = {}
            offset = 0
            for query in queries:
                candidates = dense_candidates[query.query_id][:candidate_k]
                query_scores = scores[offset : offset + len(candidates)]
                offset += len(candidates)
                full = rank_by_cross_encoder(candidates, query_scores, top_k=3)
                dense_norm = normalize([hit.score for hit in candidates])
                rerank_norm = normalize(query_scores)
                fused_scores = [
                    0.5 * dense_score + 0.5 * rerank_score
                    for dense_score, rerank_score in zip(dense_norm, rerank_norm, strict=True)
                ]
                fusion = rank_by_cross_encoder(candidates, fused_scores, top_k=3)
                ordered_probabilities = sorted(
                    (1 / (1 + math.exp(-score)) for score in query_scores), reverse=True
                )
                confident = (
                    len(ordered_probabilities) < 2
                    or ordered_probabilities[0] - ordered_probabilities[1] >= 0.15
                )
                gated = full if confident else candidates[:3]
                full_results[query.query_id] = full
                fusion_results[query.query_id] = fusion
                gated_results[query.query_id] = gated
            variants[f"{context_name}_k{candidate_k}_full"] = full_results
            variants[f"{context_name}_k{candidate_k}_fusion"] = fusion_results
            variants[f"{context_name}_k{candidate_k}_gate015"] = gated_results

    payload = {
        "experiment": "phase6_reranker_diagnostics",
        "code_revision": args.code_revision,
        "models": {
            "embedding": {"id": "BAAI/bge-m3", "revision": args.embedding_revision},
            "reranker": {"id": "BAAI/bge-reranker-v2-m3", "revision": args.reranker_revision},
        },
        "runtime": {
            "device": args.device,
            "dtype": args.dtype,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "gpu_name": torch.cuda.get_device_name(0),
            "peak_allocated_vram_mib": round(torch.cuda.max_memory_allocated() / 1024**2, 2),
            "reranker_batch_latency_ms": {
                key: [round(item, 4) for item in value] for key, value in latency.items()
            },
        },
        "query_count": len(queries),
        "diagnostic_query_count": len(diagnostic_queries),
        "strategy_constants": {"fusion_dense_weight": 0.5, "gate_probability_margin": 0.15},
        "data_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (*corpus_paths, *query_paths)
        },
        "variants": {
            name: {
                "all_queries_at_3": evaluate_retrieval(queries, results, top_k=3).model_dump(
                    mode="json"
                ),
                "diagnostic": diagnostic_metrics(diagnostic_queries, results),
                "focus_queries": {
                    query_id: [hit.evidence_id for hit in results[query_id]]
                    for query_id in ("q02", "q10", "q15")
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
