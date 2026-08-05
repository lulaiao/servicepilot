"""Stable tool error taxonomy exposed to agents and monitors."""

from enum import StrEnum


class ToolErrorCode(StrEnum):
    VALIDATION = "VALIDATION"
    NOT_FOUND = "NOT_FOUND"
    TIMEOUT = "TIMEOUT"
    TRANSIENT = "TRANSIENT"
    EMPTY_RESULT = "EMPTY_RESULT"
    PARTIAL_RESULT = "PARTIAL_RESULT"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    INTERNAL = "INTERNAL"


class TransientToolError(Exception):
    """A synthetic retryable transport failure."""


class LostResponseError(TransientToolError):
    """The write completed but its response was lost."""


class EmptyResultError(Exception):
    """A fault hook replaced a non-empty result with an empty result."""


class PartialResultError(Exception):
    """A fault hook truncated a result."""

