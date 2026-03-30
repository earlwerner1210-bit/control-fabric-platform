"""Application-level exception hierarchy."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str = "An unexpected error occurred", **extra: Any) -> None:
        self.detail = detail
        self.extra = extra
        super().__init__(detail)


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class AuthenticationError(AppError):
    status_code = 401
    code = "AUTHENTICATION_ERROR"


class AuthorizationError(AppError):
    status_code = 403
    code = "AUTHORIZATION_ERROR"


class InferenceError(AppError):
    status_code = 502
    code = "INFERENCE_ERROR"


class WorkflowError(AppError):
    status_code = 500
    code = "WORKFLOW_ERROR"


class DomainRuleViolation(AppError):
    """A deterministic business rule has been violated."""

    status_code = 422
    code = "DOMAIN_RULE_VIOLATION"

    def __init__(self, rule_name: str, detail: str, **extra: Any) -> None:
        self.rule_name = rule_name
        super().__init__(detail=detail, rule_name=rule_name, **extra)
