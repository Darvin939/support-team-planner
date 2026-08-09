class DatabaseDomainError(Exception):
    """Base class for expected persistence outcomes."""


class DuplicateEntityError(DatabaseDomainError):
    """A unique entity value already exists."""


class EntityNotFoundError(DatabaseDomainError):
    """The requested entity does not exist."""


class IntegrityConstraintError(DatabaseDomainError):
    """Expected database constraint violation with a user-facing message."""


class BulkAssignmentRescheduleError(Exception):
    """Validation error for an atomic assignment reschedule."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code
