from datetime import UTC, datetime, timedelta

import pytest

from servicepilot.memory import (
    DeterministicFactSummarizer,
    FactSource,
    InMemoryLongTermMemoryStore,
    LayeredMemory,
    LongTermCategory,
    LongTermMemoryItem,
    LongTermMemoryPolicyError,
    MemoryConsent,
    MemoryFact,
    MemoryMessage,
    MemoryRole,
    RecentMessageWindow,
    WorkingMemory,
    WorkingMemoryManager,
    run_memory_benchmark,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def fact(
    fact_id: str,
    key: str,
    value: str,
    source: FactSource,
    *,
    minutes: int = 0,
    valid_minutes: int | None = None,
    version: int | None = None,
    sensitive: bool = False,
) -> MemoryFact:
    observed = NOW + timedelta(minutes=minutes)
    return MemoryFact(
        fact_id=fact_id,
        key=key,
        value=value,
        source=source,
        observed_at=observed,
        valid_until=(
            observed + timedelta(minutes=valid_minutes)
            if valid_minutes is not None
            else None
        ),
        entity_version=version,
        sensitive=sensitive,
    )


def working() -> WorkingMemory:
    return WorkingMemory(conversation_id="conv-1", user_id="user-1")


def test_recent_window_preserves_only_last_messages_across_twenty_turns() -> None:
    window = RecentMessageWindow(capacity=6)
    for turn in range(20):
        window.append(
            MemoryMessage(
                message_id=f"message-{turn}",
                turn=turn,
                role=(MemoryRole.USER if turn % 2 == 0 else MemoryRole.ASSISTANT),
                content=f"turn {turn}",
                created_at=NOW + timedelta(minutes=turn),
            )
        )

    messages = window.snapshot()

    assert [item.turn for item in messages] == [14, 15, 16, 17, 18, 19]
    assert len(messages) == 6


def test_working_memory_keeps_order_reference_across_twenty_turns() -> None:
    manager = WorkingMemoryManager()
    memory = manager.update_fact(
        working(),
        fact("order", "order_id", "ord-20-turn", FactSource.USER),
        now=NOW,
    )
    for turn in range(1, 21):
        memory = manager.update_fact(
            memory,
            fact(
                f"topic-{turn}",
                f"topic_{turn}",
                f"value-{turn}",
                FactSource.USER,
                minutes=turn,
            ),
            now=NOW + timedelta(minutes=turn),
        )

    assert manager.resolve_reference(memory, "这单") == "ord-20-turn"


def test_realtime_tool_fact_beats_newer_wrong_summary_and_records_conflict() -> None:
    manager = WorkingMemoryManager()
    memory = manager.update_fact(
        working(),
        fact(
            "tool-status",
            "order_status",
            "refunded",
            FactSource.TOOL,
            version=3,
        ),
        now=NOW,
    )
    memory = manager.update_fact(
        memory,
        fact(
            "bad-summary",
            "order_status",
            "delivering",
            FactSource.SUMMARY,
            minutes=10,
        ),
        now=NOW + timedelta(minutes=10),
    )

    assert memory.facts["order_status"].value == "refunded"
    assert memory.conflicts[-1].selected_fact_id == "tool-status"
    assert memory.conflicts[-1].rejected_fact_id == "bad-summary"


def test_expired_transaction_fact_is_removed() -> None:
    manager = WorkingMemoryManager()
    memory = manager.update_fact(
        working(),
        fact(
            "temporary-status",
            "order_status",
            "accepted",
            FactSource.TOOL,
            valid_minutes=5,
        ),
        now=NOW,
    )

    expired = manager.expire(memory, now=NOW + timedelta(minutes=6))

    assert "order_status" not in expired.facts


def test_summary_contains_only_valid_non_sensitive_facts() -> None:
    manager = WorkingMemoryManager()
    memory = manager.update_fact(
        working(),
        fact("order", "order_id", "ord-001", FactSource.USER),
        now=NOW,
    )
    memory = manager.update_fact(
        memory,
        fact(
            "phone",
            "phone",
            "13800138000",
            FactSource.USER,
            sensitive=True,
        ),
        now=NOW,
    )

    summary = DeterministicFactSummarizer().summarize(
        memory, summary_id="summary-1", now=NOW
    )

    assert summary.text == "order_id=ord-001"
    assert all(item.source is FactSource.SUMMARY for item in summary.facts)
    assert "13800138000" not in summary.model_dump_json()


def consent(*, expires_minutes: int = 60) -> MemoryConsent:
    return MemoryConsent(
        consent_id="consent-1",
        user_id="user-1",
        purposes=("support_personalization",),
        granted_at=NOW,
        expires_at=NOW + timedelta(minutes=expires_minutes),
    )


def long_term(
    *, key: str = "preferred_contact_time", value: str = "afternoon"
) -> LongTermMemoryItem:
    return LongTermMemoryItem(
        memory_id=f"memory-{key}",
        user_id="user-1",
        category=LongTermCategory.PREFERENCE,
        key=key,
        value=value,
        purpose="support_personalization",
        consent_id="consent-1",
        created_at=NOW,
        expires_at=NOW + timedelta(days=30),
        source_conversation_id="conv-1",
    )


def test_long_term_memory_requires_consent_and_rejects_sensitive_data() -> None:
    store = InMemoryLongTermMemoryStore()
    with pytest.raises(LongTermMemoryPolicyError, match="consent"):
        store.put(long_term(), now=NOW)

    store.grant_consent(consent())
    store.put(long_term(), now=NOW)

    with pytest.raises(LongTermMemoryPolicyError, match="sensitive"):
        store.put(long_term(key="phone", value="13800138000"), now=NOW)
    assert len(store.list_user("user-1", now=NOW)) == 1


def test_long_term_memory_expiry_revoke_view_and_delete() -> None:
    store = InMemoryLongTermMemoryStore()
    store.grant_consent(consent())
    store.put(long_term(), now=NOW)
    assert store.list_user("user-1", now=NOW)[0].value == "afternoon"
    assert store.delete("memory-preferred_contact_time", user_id="user-1")
    assert store.list_user("user-1", now=NOW) == ()
    store.put(long_term(), now=NOW)

    removed = store.revoke_consent("consent-1", now=NOW + timedelta(minutes=1))
    assert removed == 1
    assert store.list_user("user-1", now=NOW + timedelta(minutes=1)) == ()

    store.grant_consent(
        consent().model_copy(update={"consent_id": "consent-2"})
    )
    expiring = long_term().model_copy(
        update={
            "memory_id": "expiring",
            "consent_id": "consent-2",
            "expires_at": NOW + timedelta(minutes=2),
        }
    )
    store.put(expiring, now=NOW)
    assert store.list_user("user-1", now=NOW + timedelta(minutes=3)) == ()


def test_wrong_memory_injection_cannot_override_tool_state() -> None:
    manager = WorkingMemoryManager()
    memory = manager.update_fact(
        working(),
        fact(
            "authoritative",
            "refunded_amount",
            "12.00",
            FactSource.TOOL,
            version=2,
        ),
        now=NOW,
    )
    injected = fact(
        "injected",
        "refunded_amount",
        "58.00",
        FactSource.LONG_TERM,
        minutes=20,
    )

    resolved = manager.update_fact(
        memory, injected, now=NOW + timedelta(minutes=20)
    )

    assert resolved.facts["refunded_amount"].value == "12.00"
    assert resolved.conflicts[-1].rejected_fact_id == "injected"


def test_layered_service_applies_summary_without_overriding_tool_fact() -> None:
    memory = LayeredMemory(
        conversation_id="conv-1", user_id="user-1", recent_capacity=4
    )
    memory.remember_fact(
        fact(
            "tool-v4",
            "order_status",
            "refunded",
            FactSource.TOOL,
            version=4,
        ),
        now=NOW,
    )
    malicious_summary = DeterministicFactSummarizer().summarize(
        WorkingMemory(
            conversation_id="conv-1",
            user_id="user-1",
            facts={
                "order_status": fact(
                    "stale",
                    "order_status",
                    "accepted",
                    FactSource.USER,
                    minutes=10,
                )
            },
        ),
        summary_id="stale-summary",
        now=NOW + timedelta(minutes=10),
    )

    memory.apply_summary(
        malicious_summary, now=NOW + timedelta(minutes=10)
    )

    context = memory.context(now=NOW + timedelta(minutes=10))
    assert context.working.facts["order_status"].value == "refunded"
    assert context.working.conflicts[-1].rejected_fact_id.startswith(
        "stale-summary:"
    )


def test_delete_user_memory_clears_all_four_layers() -> None:
    memory = LayeredMemory(conversation_id="conv-1", user_id="user-1")
    memory.record_message(
        MemoryMessage(
            message_id="message-1",
            turn=1,
            role=MemoryRole.USER,
            content="remember this",
            created_at=NOW,
        )
    )
    memory.remember_fact(
        fact("order", "order_id", "ord-delete", FactSource.USER), now=NOW
    )
    memory.create_summary(summary_id="summary-delete", now=NOW)
    memory.grant_consent(consent())
    memory.remember_long_term(long_term(), now=NOW)

    deleted = memory.delete_user_memory()
    context = memory.context(now=NOW)

    assert deleted == 1
    assert context.recent_messages == ()
    assert context.working.facts == {}
    assert context.summary is None
    assert context.long_term == ()


def test_layered_memory_benchmark_beats_no_memory_without_safety_regression() -> None:
    results = run_memory_benchmark()

    assert len(results) == 5
    assert sum(item.no_memory_success for item in results) == 2
    assert all(item.layered_memory_success for item in results)
    assert all(
        item.layered_memory_success for item in results if item.safety_case
    )
