"""Telco Ops schemas package."""

from .telco_schemas import (
    EscalationRuleObject,
    EscalationTier,
    IncidentObject,
    IncidentSeverity,
    IncidentStateObject,
    IncidentStatus,
    ServiceImpact,
    ServiceStateObject,
    SLA_TARGETS,
)

__all__ = [
    "EscalationRuleObject",
    "EscalationTier",
    "IncidentObject",
    "IncidentSeverity",
    "IncidentStateObject",
    "IncidentStatus",
    "ServiceImpact",
    "ServiceStateObject",
    "SLA_TARGETS",
]
