"""Deterministic conversion of cross-encoder scores into ranked evidence."""

from collections.abc import Sequence

from servicepilot.retrieval.models import SearchHit


def rank_by_cross_encoder(
    candidates: Sequence[SearchHit], scores: Sequence[float], *, top_k: int
) -> tuple[SearchHit, ...]:
    """Rank candidates by score with evidence ID as a stable tie-breaker."""
    if len(candidates) != len(scores):
        raise ValueError("candidate and score counts must match")
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    ranked = sorted(
        zip(scores, candidates, strict=True),
        key=lambda item: (-item[0], item[1].evidence_id),
    )
    return tuple(
        SearchHit(
            evidence_id=candidate.evidence_id,
            score=round(float(score), 8),
            rank=rank,
            text=candidate.text,
        )
        for rank, (score, candidate) in enumerate(ranked[:top_k], start=1)
    )
