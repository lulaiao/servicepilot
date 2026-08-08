"""Strongly typed working memory and deterministic factual summaries."""

from datetime import datetime

from servicepilot.memory.models import (
    FactSource,
    FactSummary,
    MemoryFact,
    WorkingMemory,
)
from servicepilot.memory.resolver import resolve_fact


class WorkingMemoryManager:
    def update_fact(
        self, memory: WorkingMemory, fact: MemoryFact, *, now: datetime
    ) -> WorkingMemory:
        current = memory.facts.get(fact.key)
        selected, conflict = resolve_fact(current, fact, now=now)
        facts = dict(memory.facts)
        if selected is None:
            facts.pop(fact.key, None)
        else:
            facts[fact.key] = selected
        conflicts = memory.conflicts + ((conflict,) if conflict else ())
        order_id = memory.last_referenced_order_id
        if fact.key == "order_id" and selected is fact:
            order_id = str(fact.value)
        return memory.model_copy(
            update={
                "facts": facts,
                "conflicts": conflicts,
                "last_referenced_order_id": order_id,
            }
        )

    @staticmethod
    def expire(memory: WorkingMemory, *, now: datetime) -> WorkingMemory:
        return memory.model_copy(
            update={
                "facts": {
                    key: fact
                    for key, fact in memory.facts.items()
                    if fact.is_valid(now)
                }
            }
        )

    @staticmethod
    def resolve_reference(memory: WorkingMemory, reference: str) -> str | None:
        if reference in {"这单", "这个订单", "它"}:
            return memory.last_referenced_order_id
        return reference or None


class DeterministicFactSummarizer:
    def summarize(
        self, memory: WorkingMemory, *, summary_id: str, now: datetime
    ) -> FactSummary:
        facts = tuple(
            fact.model_copy(
                update={
                    "fact_id": f"{summary_id}:{fact.key}",
                    "source": FactSource.SUMMARY,
                }
            )
            for _, fact in sorted(memory.facts.items())
            if fact.is_valid(now) and not fact.sensitive
        )
        text = "; ".join(f"{fact.key}={fact.value}" for fact in facts)
        return FactSummary(
            summary_id=summary_id,
            conversation_id=memory.conversation_id,
            generated_at=now,
            facts=facts,
            text=text,
        )
