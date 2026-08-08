"""Rank-only dense/lexical fusion without gold-label access."""

from collections import defaultdict

from servicepilot.retrieval.models import SearchHit


def reciprocal_rank_fusion(
    result_lists: tuple[tuple[SearchHit, ...], ...],
    *,
    top_k: int,
    constant: int = 60,
) -> tuple[SearchHit, ...]:
    scores: dict[str, float] = defaultdict(float)
    texts: dict[str, str] = {}
    for hits in result_lists:
        for hit in hits:
            scores[hit.evidence_id] += 1 / (constant + hit.rank)
            texts[hit.evidence_id] = hit.text
    ranked = sorted(scores, key=lambda item: (-scores[item], item))[:top_k]
    return tuple(
        SearchHit(
            evidence_id=evidence_id,
            score=round(scores[evidence_id], 8),
            rank=rank,
            text=texts[evidence_id],
        )
        for rank, evidence_id in enumerate(ranked, start=1)
    )
