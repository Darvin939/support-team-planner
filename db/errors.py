class IntegrityConstraintError(Exception):
    """Expected database constraint violation with a user-facing message."""


class BulkAssignmentRescheduleError(Exception):
    """Validation error for an atomic assignment reschedule."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code
