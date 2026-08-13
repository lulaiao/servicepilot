"""Typed failures raised by the deterministic business domain."""


class DomainError(Exception):
    """Base class for expected business-domain failures."""


class NotFoundError(DomainError):
    """An addressed domain entity does not exist."""


class InvalidTransitionError(DomainError):
    """A state transition is not part of the business state machine."""


class VersionConflictError(DomainError):
    """The caller attempted to mutate a stale entity version."""


class ConfirmationError(DomainError):
    """A write did not carry a matching preview confirmation."""


class IdempotencyConflictError(DomainError):
    """An idempotency key was reused with a different request."""


class PolicyViolationError(DomainError):
    """A deterministic policy assertion rejected an operation."""
