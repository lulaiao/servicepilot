#!/usr/bin/env python3
"""Attach the sealed retrieval winner to the transactional Agent and evaluate it."""

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from servicepilot.agents import RetrievalGatedTransactionalAgent, StaticPolicyEvidenceProvider
from servicepilot.agents.rule_baseline import RuleBasedSingleAgent
from servicepilot.eval import build_phase3_scenarios
from servicepilot.harness.evaluation import EvaluationHarness
from servicepilot.retrieval import SearchHit, load_policy_corpus, rank_by_cross_encoder
from servicepilot.retrieval.lexical import is_applicable
from servicepilot.retrieval.models import RetrievalQuery


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-path", type=Path, required=True)
    parser.add_argument("--embedding-revision", required=True)
    parser.add_argument("--reranker-path", type=Path, required=True)
    parser.add_argument("--reranker-revision", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def normalize(values: list[float]) -> list[float]:
    low, high = min(values), max(values)
    if low == high:
        return [0.0] * len(values)
    return [(value - low) / (high - low) for value in values]


async def main() -> None:
    args = parse_args()
    import torch
    import torch.nn.functional as functional
    from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable")
    scenarios = build_phase3_scenarios()
    policy_scenarios = tuple(item for item in scenarios if item.gold_evidence_ids)
    queries = tuple(
        RetrievalQuery(
            query_id=scenario.scenario_id,
            text=scenario.user_utterance,
            gold_evidence_ids=scenario.gold_evidence_ids,
            required_evidence_ids=scenario.gold_evidence_ids,
            policy_version="2026.1",
            business_type="food_delivery",
            order_status=scenario.initial_order_status.value,
            city="Shanghai",
        )
        for scenario in policy_scenarios
    )
    corpus_paths = (
        Path("data/policies/phase6_corpus.jsonl"),
        Path("data/policies/phase6_hard_negatives.jsonl"),
    )
    corpus = tuple(item for path in corpus_paths for item in load_policy_corpus(path))
    now = datetime(2026, 8, 8, tzinfo=UTC)
    dtype = torch.float16
    dense_tokenizer = AutoTokenizer.from_pretrained(args.embedding_path, local_files_only=True)
    dense_model = AutoModel.from_pretrained(
        args.embedding_path, local_files_only=True, torch_dtype=dtype
    ).to("cuda")
    rerank_tokenizer = AutoTokenizer.from_pretrained(args.reranker_path, local_files_only=True)
    rerank_model = AutoModelForSequenceClassification.from_pretrained(
        args.reranker_path, local_files_only=True, torch_dtype=dtype
    ).to("cuda")
    dense_model.eval()
    rerank_model.eval()

    def encode(texts: list[str]) -> Any:
        encoded = dense_tokenizer(
            texts, padding=True, truncation=True, max_length=512, return_tensors="pt"
        )
        inputs = {key: value.to("cuda") for key, value in encoded.items()}
        with torch.inference_mode():
            output = dense_model(**inputs).last_hidden_state[:, 0]
        return functional.normalize(output.float(), p=2, dim=1).cpu()

    corpus_embeddings = encode([document.text for document in corpus])
    similarities = encode([query.text for query in queries]) @ corpus_embeddings.T
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
        inputs = {key: value.to("cuda") for key, value in encoded.items()}
        with torch.inference_mode():
            scores.extend(rerank_model(**inputs).logits.reshape(-1).float().cpu().tolist())
    evidence_by_scenario: dict[str, tuple[str, ...]] = {}
    offset = 0
    for query in queries:
        current = candidates[query.query_id]
        current_scores = scores[offset : offset + len(current)]
        offset += len(current)
        fused_scores = [
            0.5 * dense_score + 0.5 * rerank_score
            for dense_score, rerank_score in zip(
                normalize([hit.score for hit in current]), normalize(current_scores), strict=True
            )
        ]
        ranked = rank_by_cross_encoder(current, fused_scores, top_k=3)
        evidence_by_scenario[query.query_id] = tuple(hit.evidence_id for hit in ranked)

    provider = StaticPolicyEvidenceProvider(evidence_by_scenario)
    baseline_harness = EvaluationHarness(code_revision=args.code_revision)
    _, baseline_results, baseline_report = await baseline_harness.run_suite(
        scenarios, agent_factory=RuleBasedSingleAgent
    )
    gated_harness = EvaluationHarness(
        code_revision=args.code_revision,
        model_revision=f"m3+v2m3-fusion:{args.embedding_revision[:8]}:{args.reranker_revision[:8]}",
        prompt_revision="plain-k6-fusion-050-050-sealed-winner",
    )
    gated_trajectories, gated_results, gated_report = await gated_harness.run_suite(
        scenarios,
        agent_factory=lambda: RetrievalGatedTransactionalAgent(provider),
    )
    required_complete = {
        scenario.scenario_id: set(scenario.gold_evidence_ids)
        <= set(evidence_by_scenario[scenario.scenario_id])
        for scenario in policy_scenarios
    }
    trajectories_by_id = {item.scenario_id: item for item in gated_trajectories}
    payload = {
        "experiment": "phase6_transactional_agent_retrieval_gate",
        "code_revision": args.code_revision,
        "locked_retrieval": {
            "candidate_k": 6,
            "dense_weight": 0.5,
            "reranker_weight": 0.5,
            "query_input": "plain",
        },
        "model_revisions": {
            "embedding": args.embedding_revision,
            "reranker": args.reranker_revision,
        },
        "scenario_sha256": hashlib.sha256(
            b"\n".join(item.model_dump_json().encode() for item in scenarios)
        ).hexdigest(),
        "policy_scenario_count": len(policy_scenarios),
        "evidence_complete_count": sum(required_complete.values()),
        "evidence_by_scenario": evidence_by_scenario,
        "baseline": baseline_report.model_dump(mode="json"),
        "retrieval_gated": gated_report.model_dump(mode="json"),
        "blocked_scenarios": [key for key, complete in required_complete.items() if not complete],
        "blocked_write_attempts": sum(
            any(
                event.tool_name
                in {
                    "cancel_order",
                    "create_refund_request",
                    "restore_coupon",
                    "reschedule_order",
                }
                for event in trajectories_by_id[scenario_id].events
            )
            for scenario_id, complete in required_complete.items()
            if not complete
        ),
        "baseline_result_count": len(baseline_results),
        "gated_result_count": len(gated_results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
