"""Typed errors for the control fabric core."""

from __future__ import annotations


class FabricError(Exception):
    """Base error for all fabric operations."""


class ControlObjectError(FabricError):
    """Error related to control object operations."""


class InvalidControlObjectError(ControlObjectError):
    """Raised when a control object fails construction validation."""


class ControlObjectStateError(ControlObjectError):
    """Raised when a lifecycle transition is invalid."""


class ControlObjectFrozenError(ControlObjectError):
    """Raised when mutation is attempted on a frozen object."""


class ControlLinkError(FabricError):
    """Error related to control link operations."""


class InvalidLinkError(ControlLinkError):
    """Raised when a link violates graph policy."""


class DuplicateLinkError(ControlLinkError):
    """Raised when a duplicate link is created."""


class GraphPolicyViolation(FabricError):
    """Raised when a graph policy constraint is violated."""


class ReconciliationError(FabricError):
    """Error during reconciliation."""


class ReasoningScopeViolation(FabricError):
    """Raised when reasoning exceeds its allowed scope."""


class ReasoningPolicyViolation(FabricError):
    """Raised when reasoning violates policy constraints."""


class ValidationChainError(FabricError):
    """Error during validation chain execution."""


class ValidationBypassAttempt(ValidationChainError):
    """Raised when validation chain bypass is attempted."""


class ActionReleaseError(FabricError):
    """Error during action release."""


class ActionWithoutValidationError(ActionReleaseError):
    """Raised when action is attempted without validation."""


class ActionWithoutEvidenceError(ActionReleaseError):
    """Raised when action is attempted without evidence."""


class RegistryError(FabricError):
    """Error in object kind registry."""


class DuplicateRegistrationError(RegistryError):
    """Raised when a kind is registered twice."""


class UnknownObjectKindError(RegistryError):
    """Raised when an unregistered object kind is referenced."""
