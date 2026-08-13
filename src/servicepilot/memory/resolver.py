"""Deterministic fact precedence, conflict and expiry rules."""

from datetime import datetime

from servicepilot.memory.models import FactConflict, FactSource, MemoryFact

SOURCE_PRIORITY = {
    FactSource.TOOL: 4,
    FactSource.USER: 3,
    FactSource.LONG_TERM: 2,
    FactSource.SUMMARY: 1,
}


def resolve_fact(
    current: MemoryFact | None,
    candidate: MemoryFact,
    *,
    now: datetime,
) -> tuple[MemoryFact | None, FactConflict | None]:
    if not candidate.is_valid(now):
        return current, None
    if current is None or not current.is_valid(now):
        return candidate, None
    if current.value == candidate.value:
        selected = max((current, candidate), key=lambda item: item.observed_at)
        return selected, None
    current_version = current.entity_version if current.entity_version is not None else -1
    candidate_version = candidate.entity_version if candidate.entity_version is not None else -1
    if candidate.source is FactSource.TOOL and current.source is FactSource.TOOL:
        selected = (
            candidate
            if (candidate_version, candidate.observed_at) > (current_version, current.observed_at)
            else current
        )
        reason = "newer authoritative tool version/time wins"
    elif SOURCE_PRIORITY[candidate.source] != SOURCE_PRIORITY[current.source]:
        selected = (
            candidate
            if SOURCE_PRIORITY[candidate.source] > SOURCE_PRIORITY[current.source]
            else current
        )
        reason = "higher-authority source wins"
    else:
        selected = candidate if candidate.observed_at > current.observed_at else current
        reason = "newer observation wins within equal authority"
    rejected = current if selected is candidate else candidate
    return selected, FactConflict(
        key=candidate.key,
        selected_fact_id=selected.fact_id,
        rejected_fact_id=rejected.fact_id,
        reason=reason,
        detected_at=now,
    )
