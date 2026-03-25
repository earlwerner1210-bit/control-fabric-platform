"""Canonicalization service business logic."""

from __future__ import annotations

import difflib
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import CanonicalEntity
from shared.telemetry.logging import get_logger

logger = get_logger("canonicalization_service")


class CanonicalizationService:
    """Resolves, registers, and merges canonical entities."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def compute_similarity(a: str, b: str) -> float:
        """Compute fuzzy similarity between two strings."""
        return difflib.SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    async def resolve_entity(
        self,
        name: str,
        entity_type: str,
        tenant_id: uuid.UUID,
        threshold: float = 0.8,
    ) -> dict[str, Any]:
        """Fuzzy-match name against the entity registry."""
        result = await self.db.execute(
            select(CanonicalEntity).where(
                CanonicalEntity.tenant_id == tenant_id,
                CanonicalEntity.entity_type == entity_type,
            )
        )
        entities = list(result.scalars().all())

        best_match: CanonicalEntity | None = None
        best_score = 0.0
        candidates: list[dict[str, Any]] = []

        for entity in entities:
            score = self.compute_similarity(name, entity.canonical_name)
            aliases = entity.aliases or []
            if isinstance(aliases, dict):
                aliases = list(aliases.values()) if aliases else []
            for alias in aliases:
                alias_score = self.compute_similarity(name, str(alias))
                score = max(score, alias_score)

            if score >= threshold:
                candidates.append({"entity": entity, "similarity": round(score, 4)})
                if score > best_score:
                    best_score = score
                    best_match = entity

        return {
            "resolved": best_match is not None,
            "entity": best_match,
            "similarity": round(best_score, 4),
            "candidates": [
                c["entity"]
                for c in sorted(candidates, key=lambda x: x["similarity"], reverse=True)[:5]
            ],
        }

    async def register_entity(
        self,
        canonical_name: str,
        entity_type: str,
        tenant_id: uuid.UUID,
        aliases: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CanonicalEntity:
        """Register a new canonical entity."""
        entity = CanonicalEntity(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            canonical_name=canonical_name,
            entity_type=entity_type,
            aliases=aliases or [],
            metadata_=metadata or {},
        )
        self.db.add(entity)
        await self.db.flush()
        logger.info("Registered entity %s (%s) for tenant %s", canonical_name, entity_type, tenant_id)
        return entity

    async def merge_entities(
        self, source_id: uuid.UUID, target_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> CanonicalEntity:
        """Merge source entity into target, combining aliases."""
        source_result = await self.db.execute(
            select(CanonicalEntity).where(CanonicalEntity.id == source_id, CanonicalEntity.tenant_id == tenant_id)
        )
        source = source_result.scalar_one_or_none()
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source entity not found")

        target_result = await self.db.execute(
            select(CanonicalEntity).where(CanonicalEntity.id == target_id, CanonicalEntity.tenant_id == tenant_id)
        )
        target = target_result.scalar_one_or_none()
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target entity not found")

        source_aliases = source.aliases if isinstance(source.aliases, list) else []
        target_aliases = target.aliases if isinstance(target.aliases, list) else []
        target.aliases = list(set(target_aliases + source_aliases + [source.canonical_name]))
        target.metadata_ = {**(target.metadata_ or {}), **(source.metadata_ or {})}

        await self.db.delete(source)
        await self.db.flush()
        logger.info("Merged entity %s into %s", source_id, target_id)
        return target

    async def get_entity(self, entity_id: uuid.UUID, tenant_id: uuid.UUID) -> CanonicalEntity:
        """Get a single entity by ID."""
        result = await self.db.execute(
            select(CanonicalEntity).where(CanonicalEntity.id == entity_id, CanonicalEntity.tenant_id == tenant_id)
        )
        entity = result.scalar_one_or_none()
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
        return entity

    async def list_entities(
        self, tenant_id: uuid.UUID, search: str | None = None, skip: int = 0, limit: int = 50
    ) -> list[CanonicalEntity]:
        """List entities with optional search."""
        stmt = select(CanonicalEntity).where(CanonicalEntity.tenant_id == tenant_id)
        if search:
            stmt = stmt.where(CanonicalEntity.canonical_name.ilike(f"%{search}%"))
        stmt = stmt.order_by(CanonicalEntity.canonical_name).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
