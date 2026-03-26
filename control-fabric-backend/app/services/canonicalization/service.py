"""Canonicalization service -- entity resolution and alias management."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass
class CanonicalEntity:
    """A canonical entity with optional aliases."""

    id: UUID
    tenant_id: UUID
    canonical_name: str
    entity_type: str
    aliases: list[str] = field(default_factory=list)


class _EntityStore:
    """In-memory canonical entity store (replaced by DB in production)."""

    def __init__(self) -> None:
        self._entities: list[CanonicalEntity] = []

    def add(self, entity: CanonicalEntity) -> None:
        self._entities.append(entity)

    def all_for_tenant(self, tenant_id: UUID, entity_type: str | None = None) -> list[CanonicalEntity]:
        results = [e for e in self._entities if e.tenant_id == tenant_id]
        if entity_type:
            results = [e for e in results if e.entity_type == entity_type]
        return results


class CanonicalizationService:
    """Maps raw / variant entity names to canonical forms."""

    def __init__(self) -> None:
        self._store = _EntityStore()

    def resolve_entity(
        self,
        tenant_id: UUID,
        raw_name: str,
        entity_type: str,
    ) -> CanonicalEntity | None:
        """Attempt to resolve *raw_name* to an existing canonical entity.

        Checks canonical names and all registered aliases (case-insensitive).
        Returns ``None`` if no match is found.
        """
        normalised = raw_name.strip().lower()
        candidates = self._store.all_for_tenant(tenant_id, entity_type)

        for entity in candidates:
            if entity.canonical_name.lower() == normalised:
                return entity
            for alias in entity.aliases:
                if alias.lower() == normalised:
                    return entity

        logger.debug(
            "canonicalization.resolve: no match for '%s' (type=%s, tenant=%s)",
            raw_name,
            entity_type,
            tenant_id,
        )
        return None

    def register_entity(
        self,
        tenant_id: UUID,
        canonical_name: str,
        entity_type: str,
        aliases: list[str] | None = None,
    ) -> CanonicalEntity:
        """Register a new canonical entity with optional aliases."""
        entity = CanonicalEntity(
            id=uuid4(),
            tenant_id=tenant_id,
            canonical_name=canonical_name,
            entity_type=entity_type,
            aliases=aliases or [],
        )
        self._store.add(entity)
        logger.info(
            "canonicalization.register: '%s' (type=%s, aliases=%d)",
            canonical_name,
            entity_type,
            len(entity.aliases),
        )
        return entity

    def find_aliases(
        self,
        tenant_id: UUID,
        entity_type: str,
        query: str,
    ) -> list[dict[str, Any]]:
        """Search canonical entities and aliases matching *query* (substring, case-insensitive)."""
        normalised = query.strip().lower()
        candidates = self._store.all_for_tenant(tenant_id, entity_type)
        results: list[dict[str, Any]] = []

        for entity in candidates:
            matched_names: list[str] = []
            if normalised in entity.canonical_name.lower():
                matched_names.append(entity.canonical_name)
            for alias in entity.aliases:
                if normalised in alias.lower():
                    matched_names.append(alias)

            if matched_names:
                results.append(
                    {
                        "entity_id": entity.id,
                        "canonical_name": entity.canonical_name,
                        "entity_type": entity.entity_type,
                        "matched": matched_names,
                    }
                )

        return results


# Singleton
canonicalization_service = CanonicalizationService()
