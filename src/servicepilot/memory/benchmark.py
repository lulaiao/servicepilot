"""Deterministic Phase 5 no-memory versus layered-memory benchmark."""

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict

from servicepilot.memory.long_term import LongTermMemoryPolicyError
from servicepilot.memory.models import (
    FactSource,
    LongTermCategory,
    LongTermMemoryItem,
    MemoryConsent,
    MemoryFact,
    MemoryMessage,
    MemoryRole,
)
from servicepilot.memory.service import LayeredMemory
from servicepilot.memory.window import RecentMessageWindow


class MemoryBenchmarkCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    no_memory_success: bool
    layered_memory_success: bool
    safety_case: bool = False
    detail: str


def run_memory_benchmark() -> tuple[MemoryBenchmarkCaseResult, ...]:
    now = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    return (
        _cross_twenty_turns(now),
        _consented_preference(now),
        _tool_summary_conflict(now),
        _expired_state_abstention(now),
        _sensitive_data_rejection(now),
    )


def _cross_twenty_turns(now: datetime) -> MemoryBenchmarkCaseResult:
    recent_only = RecentMessageWindow(capacity=6)
    layered = LayeredMemory(conversation_id="benchmark-20-turn", user_id="benchmark-user")
    layered.remember_fact(
        MemoryFact(
            fact_id="order-reference",
            key="order_id",
            value="ord-memory-20",
            source=FactSource.USER,
            observed_at=now,
        ),
        now=now,
    )
    for turn in range(20):
        message = MemoryMessage(
            message_id=f"turn-{turn}",
            turn=turn,
            role=MemoryRole.USER,
            content=("订单 ord-memory-20" if turn == 0 else f"filler {turn}"),
            created_at=now + timedelta(minutes=turn),
        )
        recent_only.append(message)
        layered.record_message(message)
    no_memory_resolved = any("ord-memory-20" in item.content for item in recent_only.snapshot())
    layered_resolved = layered.resolve_reference("这单") == "ord-memory-20"
    return MemoryBenchmarkCaseResult(
        case_id="cross_20_turn_reference",
        no_memory_success=no_memory_resolved,
        layered_memory_success=layered_resolved,
        detail="Working memory retains the typed order reference beyond the window.",
    )


def _consented_preference(now: datetime) -> MemoryBenchmarkCaseResult:
    layered = LayeredMemory(conversation_id="benchmark-preference", user_id="benchmark-user")
    layered.grant_consent(
        MemoryConsent(
            consent_id="benchmark-consent",
            user_id="benchmark-user",
            purposes=("support_personalization",),
            granted_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    layered.remember_long_term(
        LongTermMemoryItem(
            memory_id="preferred-contact-time",
            user_id="benchmark-user",
            category=LongTermCategory.PREFERENCE,
            key="preferred_contact_time",
            value="afternoon",
            purpose="support_personalization",
            consent_id="benchmark-consent",
            created_at=now,
            expires_at=now + timedelta(days=7),
            source_conversation_id="benchmark-preference",
        ),
        now=now,
    )
    remembered = layered.context(now=now).long_term[0].value == "afternoon"
    return MemoryBenchmarkCaseResult(
        case_id="consented_preference",
        no_memory_success=False,
        layered_memory_success=remembered,
        detail="Only consented, purpose-bound long-term memory retains preference.",
    )


def _tool_summary_conflict(now: datetime) -> MemoryBenchmarkCaseResult:
    layered = LayeredMemory(conversation_id="benchmark-conflict", user_id="benchmark-user")
    layered.remember_fact(
        MemoryFact(
            fact_id="tool-refunded-v3",
            key="order_status",
            value="refunded",
            source=FactSource.TOOL,
            observed_at=now,
            entity_version=3,
        ),
        now=now,
    )
    layered.remember_fact(
        MemoryFact(
            fact_id="wrong-summary",
            key="order_status",
            value="delivering",
            source=FactSource.SUMMARY,
            observed_at=now + timedelta(minutes=10),
        ),
        now=now + timedelta(minutes=10),
    )
    resolved = layered.context(now=now + timedelta(minutes=10)).working.facts["order_status"].value
    return MemoryBenchmarkCaseResult(
        case_id="tool_over_stale_summary",
        no_memory_success=False,
        layered_memory_success=resolved == "refunded",
        safety_case=True,
        detail="Authoritative tool state beats a newer contradictory summary.",
    )


def _expired_state_abstention(now: datetime) -> MemoryBenchmarkCaseResult:
    layered = LayeredMemory(conversation_id="benchmark-expiry", user_id="benchmark-user")
    layered.remember_fact(
        MemoryFact(
            fact_id="temporary-status",
            key="order_status",
            value="accepted",
            source=FactSource.TOOL,
            observed_at=now,
            valid_until=now + timedelta(minutes=5),
        ),
        now=now,
    )
    abstained = "order_status" not in layered.context(now=now + timedelta(minutes=6)).working.facts
    return MemoryBenchmarkCaseResult(
        case_id="expired_state_abstention",
        no_memory_success=True,
        layered_memory_success=abstained,
        safety_case=True,
        detail="Both no-memory and layered memory avoid asserting expired state.",
    )


def _sensitive_data_rejection(now: datetime) -> MemoryBenchmarkCaseResult:
    layered = LayeredMemory(conversation_id="benchmark-privacy", user_id="benchmark-user")
    layered.grant_consent(
        MemoryConsent(
            consent_id="privacy-consent",
            user_id="benchmark-user",
            purposes=("support_personalization",),
            granted_at=now,
        )
    )
    rejected = False
    try:
        layered.remember_long_term(
            LongTermMemoryItem(
                memory_id="forbidden-phone",
                user_id="benchmark-user",
                category=LongTermCategory.PREFERENCE,
                key="phone",
                value="13800138000",
                purpose="support_personalization",
                consent_id="privacy-consent",
                created_at=now,
                expires_at=now + timedelta(days=1),
                source_conversation_id="benchmark-privacy",
            ),
            now=now,
        )
    except LongTermMemoryPolicyError:
        rejected = True
    return MemoryBenchmarkCaseResult(
        case_id="sensitive_long_term_rejection",
        no_memory_success=True,
        layered_memory_success=rejected,
        safety_case=True,
        detail="No-memory stores nothing; layered memory explicitly rejects sensitive data.",
    )
