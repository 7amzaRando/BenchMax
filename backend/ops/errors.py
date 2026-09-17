"""Typed service-layer errors for BenchMax operations.

Why this module exists (architecture audit M6): ``backend/operations.py``
control-plane functions historically returned plain strings
(``"Run not found."``, ``"Cannot pause …"``), so the API layer could only
return HTTP 200 with error text. New code raises these typed errors;
``backend/api.py`` maps them to HTTP status codes (404/409/400), while the
legacy string-returning functions are kept for back-compat and translated
by message content at the API boundary.
"""


class BenchMaxError(Exception):
    """Base class for all BenchMax service errors."""


class RunNotFoundError(BenchMaxError, ValueError):
    """Raised when a run ID does not exist.

    Also a ValueError for back-compat: service code historically raised
    ``ValueError("Run … not found")`` and callers/tests pin that contract.
    """

    def __init__(self, run_id) -> None:
        super().__init__(f"Run {run_id} not found.")
        self.run_id = run_id


class RunStateError(BenchMaxError):
    """Raised when an operation is invalid for the run's current status."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class NoValidIdsError(BenchMaxError):
    """Raised when a bulk-ID parameter contains no usable run IDs."""

    def __init__(self, message: str = "No valid run IDs provided.") -> None:
        super().__init__(message)


class NothingToExportError(BenchMaxError):
    """Raised when an export has no rows to write (maps to HTTP 404)."""

    def __init__(self, message: str = "Nothing to export.") -> None:
        super().__init__(message)
