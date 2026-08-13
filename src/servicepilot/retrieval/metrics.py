"""Deterministic evidence-retrieval metrics."""

import math

from servicepilot.retrieval.models import RetrievalMetrics, RetrievalQuery, SearchHit


def evaluate_retrieval(
    queries: tuple[RetrievalQuery, ...],
    results: dict[str, tuple[SearchHit, ...]],
    *,
    top_k: int,
) -> RetrievalMetrics:
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcgs: list[float] = []
    citation_accuracies: list[float] = []
    for query in queries:
        hits = results[query.query_id][:top_k]
        returned = [item.evidence_id for item in hits]
        gold = set(query.gold_evidence_ids)
        relevant = [identifier in gold for identifier in returned]
        recalls.append(len(set(returned) & gold) / len(gold))
        first_rank = next(
            (rank for rank, is_relevant in enumerate(relevant, start=1) if is_relevant),
            None,
        )
        reciprocal_ranks.append(0.0 if first_rank is None else 1 / first_rank)
        discounted_gain = sum(
            1 / math.log2(rank + 1)
            for rank, is_relevant in enumerate(relevant, start=1)
            if is_relevant
        )
        ideal_gain = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(gold), top_k) + 1))
        ndcgs.append(discounted_gain / ideal_gain)
        citation_accuracies.append(
            0.0 if not returned else len(set(returned) & gold) / len(returned)
        )
    count = len(queries)
    return RetrievalMetrics(
        query_count=count,
        recall_at_k=round(sum(recalls) / count, 4),
        mean_reciprocal_rank=round(sum(reciprocal_ranks) / count, 4),
        ndcg_at_k=round(sum(ndcgs) / count, 4),
        citation_accuracy_at_k=round(sum(citation_accuracies) / count, 4),
    )
