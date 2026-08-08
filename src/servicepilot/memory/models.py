"""Typed contracts for the four-layer memory system."""

from datetime import datetime
from enum import StrEnum
from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, Field

MemoryScalar: TypeAlias = str | int | float | bool


class MemoryRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FactSource(StrEnum):
    TOOL = "tool"
    USER = "user"
    SUMMARY = "summary"
    LONG_TERM = "long_term"


class LongTermCategory(StrEnum):
    PREFERENCE = "preference"
    HISTORY = "history"


class MemoryMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_id: str
    turn: int = Field(ge=0)
    role: MemoryRole
    content: str
    created_at: datetime


class MemoryFact(BaseModel):
    model_config = ConfigDict(frozen=True)

    fact_id: str
    key: str
    value: MemoryScalar
    source: FactSource
    observed_at: datetime
    valid_until: datetime | None = None
    entity_version: int | None = Field(default=None, ge=0)
    confidence: float = Field(default=1.0, ge=0, le=1)
    sensitive: bool = False

    def is_valid(self, now: datetime) -> bool:
        return self.valid_until is None or now < self.valid_until


class FactConflict(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    selected_fact_id: str
    rejected_fact_id: str
    reason: str
    detected_at: datetime


class WorkingMemory(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversation_id: str
    user_id: str
    goal: str | None = None
    confirmed_slots: dict[str, str] = Field(default_factory=dict)
    facts: dict[str, MemoryFact] = Field(default_factory=dict)
    conflicts: tuple[FactConflict, ...] = ()
    last_referenced_order_id: str | None = None


class FactSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary_id: str
    conversation_id: str
    generated_at: datetime
    facts: tuple[MemoryFact, ...]
    text: str


class MemoryConsent(BaseModel):
    model_config = ConfigDict(frozen=True)

    consent_id: str
    user_id: str
    purposes: tuple[str, ...]
    granted_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def permits(self, purpose: str, now: datetime) -> bool:
        return (
            purpose in self.purposes
            and self.revoked_at is None
            and (self.expires_at is None or now < self.expires_at)
        )


class LongTermMemoryItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    memory_id: str
    user_id: str
    category: LongTermCategory
    key: str
    value: MemoryScalar
    purpose: str
    consent_id: str
    created_at: datetime
    expires_at: datetime
    source_conversation_id: str

    def is_valid(self, now: datetime) -> bool:
        return now < self.expires_at


class ResolvedMemoryContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    recent_messages: tuple[MemoryMessage, ...]
    working: WorkingMemory
    summary: FactSummary | None = None
    long_term: tuple[LongTermMemoryItem, ...] = ()
