"""
SLM Router — Domain Model Selector

Routes inference requests to the appropriate domain SLM based on
operational_plane and object_type. Falls back to the generic model
when no domain SLM is registered for the context.

Patent relevance: Domain SLMs are still subordinate utilities.
Their output is always a TypedHypothesis that passes through the
same deterministic validation chain. No domain SLM can bypass the gate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SLMContext:
    """Context extracted from an inference request for routing decisions."""

    operational_plane: str
    object_types: list[str]
    hypothesis_type: str
    domain_pack: str | None = None
    regulatory_context: list[str] = field(default_factory=list)


@dataclass
class DomainHypothesisEnrichment:
    """Domain-specific enrichment added to a hypothesis by a domain SLM."""

    regulation_citations: list[str] = field(default_factory=list)
    specific_clause: str = ""
    domain_specific_risk: str = ""
    prescribed_evidence_types: list[str] = field(default_factory=list)
    remediation_precision: str = ""
    confidence_boost: float = 0.0


class DomainSLMAdapter:
    """
    Base class for all domain SLM adapters.
    Every domain SLM must implement enrich_hypothesis().

    Domain SLMs do NOT generate hypothesis titles or findings —
    they enrich hypotheses that the core inference engine has already generated.
    This preserves the architectural invariant that AI output is typed and bounded.
    """

    adapter_id: str = "base"
    domain_name: str = "generic"
    supported_planes: list[str] = []
    supported_object_types: list[str] = []

    def can_handle(self, context: SLMContext) -> bool:
        """Return True if this adapter is appropriate for the given context."""
        plane_match = (
            not self.supported_planes or context.operational_plane in self.supported_planes
        )
        type_match = not self.supported_object_types or any(
            t in self.supported_object_types for t in context.object_types
        )
        return plane_match and type_match

    def enrich_hypothesis(
        self,
        hypothesis_text: str,
        context: SLMContext,
        control_objects: list[dict],
    ) -> DomainHypothesisEnrichment:
        """Enrich a hypothesis with domain-specific regulatory knowledge."""
        return DomainHypothesisEnrichment()

    def get_regulatory_context(self, plane: str, object_types: list[str]) -> list[str]:
        """Return relevant regulatory frameworks for this context."""
        return []


class SLMRouter:
    """
    Routes inference requests to the appropriate domain SLM adapter.

    Registration: domain packs register their SLM adapter when loaded.
    Fallback: generic model when no domain SLM is registered.
    """

    def __init__(self) -> None:
        self._adapters: list[DomainSLMAdapter] = []
        self._default_adapter = DomainSLMAdapter()

    def register(self, adapter: DomainSLMAdapter) -> None:
        """Register a domain SLM adapter."""
        self._adapters.append(adapter)
        logger.info(
            "SLM adapter registered: %s (domain=%s planes=%s)",
            adapter.adapter_id,
            adapter.domain_name,
            adapter.supported_planes,
        )

    def route(self, context: SLMContext) -> DomainSLMAdapter:
        """Select the best adapter for this context."""
        candidates = [a for a in self._adapters if a.can_handle(context)]
        if not candidates:
            logger.debug(
                "SLMRouter: no domain adapter for plane=%s, using generic",
                context.operational_plane,
            )
            return self._default_adapter
        best = max(
            candidates,
            key=lambda a: len(a.supported_planes) + len(a.supported_object_types),
        )
        logger.debug(
            "SLMRouter: routing to %s for plane=%s",
            best.adapter_id,
            context.operational_plane,
        )
        return best

    def enrich(
        self,
        hypothesis_text: str,
        context: SLMContext,
        control_objects: list[dict],
    ) -> DomainHypothesisEnrichment:
        """Route and enrich a hypothesis."""
        adapter = self.route(context)
        try:
            return adapter.enrich_hypothesis(hypothesis_text, context, control_objects)
        except Exception as e:
            logger.error("SLM enrichment failed (adapter=%s): %s", adapter.adapter_id, e)
            return DomainHypothesisEnrichment()

    def list_adapters(self) -> list[dict]:
        return [
            {
                "adapter_id": a.adapter_id,
                "domain": a.domain_name,
                "planes": a.supported_planes,
                "object_types": a.supported_object_types,
            }
            for a in self._adapters
        ]

    @property
    def adapter_count(self) -> int:
        return len(self._adapters)


# Module-level singleton
slm_router = SLMRouter()
