"""Composition service for recent, working, summary and long-term memory."""

from datetime import datetime

from servicepilot.memory.long_term import InMemoryLongTermMemoryStore
from servicepilot.memory.models import (
    FactSummary,
    LongTermMemoryItem,
    MemoryConsent,
    MemoryFact,
    MemoryMessage,
    ResolvedMemoryContext,
    WorkingMemory,
)
from servicepilot.memory.window import RecentMessageWindow
from servicepilot.memory.working import (
    DeterministicFactSummarizer,
    WorkingMemoryManager,
)


class LayeredMemory:
    def __init__(
        self,
        *,
        conversation_id: str,
        user_id: str,
        recent_capacity: int = 8,
        long_term_store: InMemoryLongTermMemoryStore | None = None,
    ) -> None:
        self.recent = RecentMessageWindow(recent_capacity)
        self.working = WorkingMemory(conversation_id=conversation_id, user_id=user_id)
        self.summary: FactSummary | None = None
        self.long_term_store = long_term_store or InMemoryLongTermMemoryStore()
        self._working_manager = WorkingMemoryManager()
        self._summarizer = DeterministicFactSummarizer()

    def record_message(self, message: MemoryMessage) -> None:
        self.recent.append(message)

    def remember_fact(self, fact: MemoryFact, *, now: datetime) -> None:
        self.working = self._working_manager.update_fact(self.working, fact, now=now)

    def create_summary(self, *, summary_id: str, now: datetime) -> FactSummary:
        self.summary = self._summarizer.summarize(self.working, summary_id=summary_id, now=now)
        return self.summary

    def apply_summary(self, summary: FactSummary, *, now: datetime) -> None:
        if summary.conversation_id != self.working.conversation_id:
            raise ValueError("summary belongs to a different conversation")
        for fact in summary.facts:
            self.remember_fact(fact, now=now)
        self.summary = summary

    def grant_consent(self, consent: MemoryConsent) -> None:
        if consent.user_id != self.working.user_id:
            raise ValueError("consent belongs to a different user")
        self.long_term_store.grant_consent(consent)

    def remember_long_term(self, item: LongTermMemoryItem, *, now: datetime) -> None:
        if item.user_id != self.working.user_id:
            raise ValueError("long-term item belongs to a different user")
        self.long_term_store.put(item, now=now)

    def context(self, *, now: datetime) -> ResolvedMemoryContext:
        self.working = self._working_manager.expire(self.working, now=now)
        return ResolvedMemoryContext(
            recent_messages=self.recent.snapshot(),
            working=self.working,
            summary=self.summary,
            long_term=self.long_term_store.list_user(self.working.user_id, now=now),
        )

    def resolve_reference(self, reference: str) -> str | None:
        return self._working_manager.resolve_reference(self.working, reference)

    def delete_user_memory(self) -> int:
        deleted = self.long_term_store.delete_user(self.working.user_id)
        self.recent.clear()
        self.working = WorkingMemory(
            conversation_id=self.working.conversation_id,
            user_id=self.working.user_id,
        )
        self.summary = None
        return deleted
