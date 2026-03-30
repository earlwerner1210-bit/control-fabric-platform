"""Entity canonicalization service – alias resolution and fuzzy matching."""

from __future__ import annotations

import uuid
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import CanonicalEntity

logger = get_logger("canonicalization")

SIMILARITY_THRESHOLD = 0.8


class CanonicalizationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def resolve_entity(
        self,
        name: str,
        entity_type: str,
        tenant_id: uuid.UUID,
        source_document_id: uuid.UUID | None = None,
    ) -> CanonicalEntity:
        """Resolve a name to an existing canonical entity or create a new one."""
        match = await self._find_best_match(name, entity_type, tenant_id)
        if match:
            # Add alias if new
            aliases = match.aliases or []
            if name not in aliases and name != match.canonical_name:
                aliases.append(name)
                match.aliases = aliases
                await self.db.flush()
            return match

        # Create new canonical entity
        entity = CanonicalEntity(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            canonical_name=name,
            entity_type=entity_type,
            aliases=[],
            confidence=1.0,
            source_document_id=source_document_id,
        )
        self.db.add(entity)
        await self.db.flush()
        logger.info("entity_created", name=name, entity_type=entity_type)
        return entity

    async def _find_best_match(
        self, name: str, entity_type: str, tenant_id: uuid.UUID
    ) -> CanonicalEntity | None:
        result = await self.db.execute(
            select(CanonicalEntity).where(
                CanonicalEntity.tenant_id == tenant_id,
                CanonicalEntity.entity_type == entity_type,
            )
        )
        entities = result.scalars().all()

        best_match: CanonicalEntity | None = None
        best_score = 0.0

        for entity in entities:
            score = self._compute_similarity(name, entity.canonical_name)
            # Also check aliases
            for alias in entity.aliases or []:
                alias_score = self._compute_similarity(name, alias)
                score = max(score, alias_score)

            if score > best_score and score >= SIMILARITY_THRESHOLD:
                best_score = score
                best_match = entity

        return best_match

    def _compute_similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

    async def list_entities(
        self, tenant_id: uuid.UUID, entity_type: str | None = None
    ) -> list[CanonicalEntity]:
        stmt = select(CanonicalEntity).where(CanonicalEntity.tenant_id == tenant_id)
        if entity_type:
            stmt = stmt.where(CanonicalEntity.entity_type == entity_type)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def merge_entities(
        self, source_id: uuid.UUID, target_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> CanonicalEntity:
        source = (
            await self.db.execute(select(CanonicalEntity).where(CanonicalEntity.id == source_id))
        ).scalar_one()
        target = (
            await self.db.execute(select(CanonicalEntity).where(CanonicalEntity.id == target_id))
        ).scalar_one()

        # Merge aliases
        target_aliases = target.aliases or []
        target_aliases.append(source.canonical_name)
        for alias in source.aliases or []:
            if alias not in target_aliases:
                target_aliases.append(alias)
        target.aliases = target_aliases

        await self.db.delete(source)
        await self.db.flush()
        logger.info("entities_merged", source=str(source_id), target=str(target_id))
        return target
