"""Application-level exception hierarchy."""

from __future__ import annotations


class AppError(Exception):
    """Base exception for all application errors.

    Attributes:
        status_code: HTTP status code to surface in API responses.
        detail: Human-readable error description.
        code: Machine-readable error code for clients.
    """

    def __init__(
        self,
        *,
        status_code: int = 500,
        detail: str = "Internal server error",
        code: str = "INTERNAL_ERROR",
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, detail: str = "Resource not found", code: str = "NOT_FOUND") -> None:
        super().__init__(status_code=404, detail=detail, code=code)


class ValidationError(AppError):
    """Raised when input data fails validation rules."""

    def __init__(self, detail: str = "Validation failed", code: str = "VALIDATION_ERROR") -> None:
        super().__init__(status_code=422, detail=detail, code=code)


class AuthenticationError(AppError):
    """Raised when authentication credentials are missing or invalid."""

    def __init__(
        self, detail: str = "Authentication required", code: str = "AUTHENTICATION_ERROR"
    ) -> None:
        super().__init__(status_code=401, detail=detail, code=code)


class AuthorizationError(AppError):
    """Raised when an authenticated user lacks required permissions."""

    def __init__(
        self, detail: str = "Permission denied", code: str = "AUTHORIZATION_ERROR"
    ) -> None:
        super().__init__(status_code=403, detail=detail, code=code)


class ConflictError(AppError):
    """Raised when an operation conflicts with existing state."""

    def __init__(self, detail: str = "Conflict", code: str = "CONFLICT") -> None:
        super().__init__(status_code=409, detail=detail, code=code)
