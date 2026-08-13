"""Consent-, expiry- and privacy-controlled long-term memory adapter."""

import re
from datetime import datetime
from threading import RLock

from servicepilot.memory.models import LongTermMemoryItem, MemoryConsent


class LongTermMemoryPolicyError(ValueError):
    pass


SENSITIVE_KEY_MARKERS = {
    "phone",
    "mobile",
    "email",
    "address",
    "id_card",
    "payment_card",
    "password",
    "token",
}


def is_sensitive(key: str, value: object) -> bool:
    normalized = key.lower()
    if any(marker in normalized for marker in SENSITIVE_KEY_MARKERS):
        return True
    text = str(value)
    return bool(
        re.search(r"\b1[3-9]\d{9}\b", text) or re.search(r"\b\d{15,19}\b", text) or "@" in text
    )


class InMemoryLongTermMemoryStore:
    def __init__(self) -> None:
        self._items: dict[str, LongTermMemoryItem] = {}
        self._consents: dict[str, MemoryConsent] = {}
        self._lock = RLock()

    def grant_consent(self, consent: MemoryConsent) -> None:
        with self._lock:
            self._consents[consent.consent_id] = consent

    def revoke_consent(self, consent_id: str, *, now: datetime) -> int:
        with self._lock:
            consent = self._consents[consent_id]
            self._consents[consent_id] = consent.model_copy(update={"revoked_at": now})
            targets = [key for key, item in self._items.items() if item.consent_id == consent_id]
            for key in targets:
                del self._items[key]
            return len(targets)

    def put(self, item: LongTermMemoryItem, *, now: datetime) -> None:
        with self._lock:
            consent = self._consents.get(item.consent_id)
            if consent is None or consent.user_id != item.user_id:
                raise LongTermMemoryPolicyError("valid user consent is required")
            if not consent.permits(item.purpose, now):
                raise LongTermMemoryPolicyError("consent does not permit this purpose")
            if not item.is_valid(now):
                raise LongTermMemoryPolicyError("memory is already expired")
            if is_sensitive(item.key, item.value):
                raise LongTermMemoryPolicyError("sensitive long-term memory is forbidden")
            self._items[item.memory_id] = item

    def list_user(self, user_id: str, *, now: datetime) -> tuple[LongTermMemoryItem, ...]:
        with self._lock:
            self._purge_expired(now)
            return tuple(item for item in self._items.values() if item.user_id == user_id)

    def delete_user(self, user_id: str) -> int:
        with self._lock:
            targets = [key for key, item in self._items.items() if item.user_id == user_id]
            for key in targets:
                del self._items[key]
            return len(targets)

    def delete(self, memory_id: str, *, user_id: str) -> bool:
        with self._lock:
            item = self._items.get(memory_id)
            if item is None or item.user_id != user_id:
                return False
            del self._items[memory_id]
            return True

    def _purge_expired(self, now: datetime) -> None:
        targets = [key for key, item in self._items.items() if not item.is_valid(now)]
        for key in targets:
            del self._items[key]
