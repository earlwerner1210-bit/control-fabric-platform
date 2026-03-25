"""Retrieval service – keyword, vector, and hybrid search."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import DocumentChunk
from app.services.embedding.service import EmbeddingProvider, get_embedding_provider

logger = get_logger("retrieval")


@dataclass
class RetrievalResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float
    metadata: dict | None = None


@dataclass
class ChunkResult:
    """Rich result object for retrieval operations."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    text: str
    score: float
    metadata: dict | None = None


@dataclass
class Citation:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content_excerpt: str
    relevance_score: float


class RetrievalService:
    def __init__(self, db: AsyncSession, embedding_provider: EmbeddingProvider | None = None) -> None:
        self.db = db
        self.embedding_provider = embedding_provider or get_embedding_provider()

    async def search(
        self,
        query: str,
        tenant_id: uuid.UUID,
        mode: str = "hybrid",
        top_k: int = 10,
        document_type: str | None = None,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[RetrievalResult]:
        if mode == "keyword":
            return await self.keyword_search(query, tenant_id, top_k, document_type, document_ids)
        elif mode == "vector":
            return await self.vector_search(query, tenant_id, top_k, document_type, document_ids)
        else:
            return await self.hybrid_search(query, tenant_id, top_k, document_type, document_ids)

    async def keyword_search(
        self,
        query: str,
        tenant_id: uuid.UUID,
        top_k: int = 10,
        document_type: str | None = None,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[RetrievalResult]:
        stmt = select(DocumentChunk).where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.content.ilike(f"%{query}%"),
        )
        if document_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))
        stmt = stmt.limit(top_k)
        result = await self.db.execute(stmt)
        chunks = result.scalars().all()
        return [
            RetrievalResult(
                chunk_id=c.id,
                document_id=c.document_id,
                content=c.content,
                score=1.0,
                metadata=c.metadata_,
            )
            for c in chunks
        ]

    async def vector_search(
        self,
        query: str,
        tenant_id: uuid.UUID,
        top_k: int = 10,
        document_type: str | None = None,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[RetrievalResult]:
        query_embedding = (await self.embedding_provider.embed([query]))[0]
        # Use pgvector cosine distance
        stmt = (
            select(
                DocumentChunk,
                DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.embedding.isnot(None),
            )
            .order_by("distance")
            .limit(top_k)
        )
        if document_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))
        result = await self.db.execute(stmt)
        rows = result.all()
        return [
            RetrievalResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                score=1.0 - distance,
                metadata=chunk.metadata_,
            )
            for chunk, distance in rows
        ]

    async def hybrid_search(
        self,
        query: str,
        tenant_id: uuid.UUID,
        top_k: int = 10,
        document_type: str | None = None,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[RetrievalResult]:
        """Reciprocal Rank Fusion of keyword + vector results."""
        keyword_results = await self.keyword_search(query, tenant_id, top_k * 2, document_type, document_ids)
        vector_results = await self.vector_search(query, tenant_id, top_k * 2, document_type, document_ids)

        # RRF with k=60
        k = 60
        scores: dict[uuid.UUID, float] = {}
        result_map: dict[uuid.UUID, RetrievalResult] = {}

        for rank, r in enumerate(keyword_results):
            scores[r.chunk_id] = scores.get(r.chunk_id, 0) + 1.0 / (k + rank + 1)
            result_map[r.chunk_id] = r

        for rank, r in enumerate(vector_results):
            scores[r.chunk_id] = scores.get(r.chunk_id, 0) + 1.0 / (k + rank + 1)
            result_map[r.chunk_id] = r

        sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:top_k]
        return [
            RetrievalResult(
                chunk_id=cid,
                document_id=result_map[cid].document_id,
                content=result_map[cid].content,
                score=scores[cid],
                metadata=result_map[cid].metadata,
            )
            for cid in sorted_ids
        ]

    def build_citations(self, results: list[RetrievalResult]) -> list[Citation]:
        return [
            Citation(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                content_excerpt=r.content[:200],
                relevance_score=r.score,
            )
            for r in results
        ]

    # ── High-level retrieval helpers ──────────────────────────────

    async def retrieve_relevant_context(
        self,
        tenant_id: uuid.UUID,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[ChunkResult]:
        """Retrieve context chunks relevant to *query* for a tenant.

        *filters* may contain ``document_type`` and/or ``document_ids`` to
        narrow the search scope.  Delegates to ``hybrid_search`` internally.
        """
        doc_type = (filters or {}).get("document_type")
        doc_ids = (filters or {}).get("document_ids")
        results = await self.search(
            query=query,
            tenant_id=tenant_id,
            mode="hybrid",
            top_k=top_k,
            document_type=doc_type,
            document_ids=doc_ids,
        )
        return [
            ChunkResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                text=r.content,
                score=r.score,
                metadata=r.metadata,
            )
            for r in results
        ]

    async def retrieve_by_document(
        self,
        document_id: uuid.UUID,
        query: str,
        top_k: int = 10,
    ) -> list[ChunkResult]:
        """Retrieve the most relevant chunks from a single document."""
        # Use the tenant_id from the first matching chunk (scoped to document)
        result = await self.db.execute(
            select(DocumentChunk.tenant_id)
            .where(DocumentChunk.document_id == document_id)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return []
        tenant_id = row

        results = await self.search(
            query=query,
            tenant_id=tenant_id,
            mode="hybrid",
            top_k=top_k,
            document_ids=[document_id],
        )
        return [
            ChunkResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                text=r.content,
                score=r.score,
                metadata=r.metadata,
            )
            for r in results
        ]

    async def hybrid_search_weighted(
        self,
        tenant_id: uuid.UUID,
        query: str,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7,
        top_k: int = 10,
        document_type: str | None = None,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[ChunkResult]:
        """Weighted hybrid search combining keyword and semantic scores.

        Unlike the base ``hybrid_search`` (which uses Reciprocal Rank Fusion),
        this method normalises scores from each leg and applies explicit
        ``keyword_weight`` / ``semantic_weight`` multipliers before merging.
        """
        keyword_results = await self.keyword_search(
            query, tenant_id, top_k * 2, document_type, document_ids
        )
        vector_results = await self.vector_search(
            query, tenant_id, top_k * 2, document_type, document_ids
        )

        # Normalise keyword scores to [0, 1]
        kw_max = max((r.score for r in keyword_results), default=1.0) or 1.0
        kw_scores: dict[uuid.UUID, float] = {
            r.chunk_id: (r.score / kw_max) * keyword_weight for r in keyword_results
        }

        # Normalise vector scores to [0, 1]
        vec_max = max((r.score for r in vector_results), default=1.0) or 1.0
        vec_scores: dict[uuid.UUID, float] = {
            r.chunk_id: (r.score / vec_max) * semantic_weight for r in vector_results
        }

        # Merge
        all_ids = set(kw_scores) | set(vec_scores)
        result_map: dict[uuid.UUID, RetrievalResult] = {}
        for r in keyword_results:
            result_map.setdefault(r.chunk_id, r)
        for r in vector_results:
            result_map.setdefault(r.chunk_id, r)

        merged: list[tuple[uuid.UUID, float]] = []
        for cid in all_ids:
            combined = kw_scores.get(cid, 0.0) + vec_scores.get(cid, 0.0)
            merged.append((cid, combined))

        merged.sort(key=lambda t: t[1], reverse=True)

        return [
            ChunkResult(
                chunk_id=cid,
                document_id=result_map[cid].document_id,
                text=result_map[cid].content,
                score=score,
                metadata=result_map[cid].metadata,
            )
            for cid, score in merged[:top_k]
        ]
