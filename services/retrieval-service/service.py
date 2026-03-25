"""Retrieval service business logic."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.models import DocumentChunk
from shared.telemetry.logging import get_logger

logger = get_logger("retrieval_service")


class RetrievalService:
    """Multi-mode retrieval: keyword, vector, and hybrid search."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._settings = get_settings()

    async def keyword_search(
        self, query: str, tenant_id: uuid.UUID, filters: dict[str, Any], top_k: int
    ) -> list[dict[str, Any]]:
        """SQL LIKE keyword search."""
        like_pattern = f"%{query}%"
        stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                DocumentChunk.chunk_index,
                DocumentChunk.content,
            )
            .where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.content.ilike(like_pattern),
            )
            .limit(top_k)
        )
        if "document_id" in filters:
            stmt = stmt.where(DocumentChunk.document_id == filters["document_id"])

        result = await self.db.execute(stmt)
        rows = result.all()
        scored: list[dict[str, Any]] = []
        for row in rows:
            content_lower = row.content.lower()
            query_lower = query.lower()
            occurrences = content_lower.count(query_lower)
            score = min(occurrences / max(len(content_lower.split()), 1), 1.0)
            scored.append({
                "chunk_id": row.id,
                "document_id": row.document_id,
                "chunk_index": row.chunk_index,
                "text_snippet": row.content[:300],
                "score": round(score, 4),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    async def vector_search(
        self, query: str, tenant_id: uuid.UUID, filters: dict[str, Any], top_k: int
    ) -> list[dict[str, Any]]:
        """pgvector cosine-similarity search."""
        settings = self._settings
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={"input": [query], "model": settings.EMBEDDING_MODEL},
                )
                resp.raise_for_status()
                query_vector = resp.json()["data"][0]["embedding"]
        except Exception:
            logger.warning("Failed to generate query embedding, falling back to keyword search")
            return await self.keyword_search(query, tenant_id, filters, top_k)

        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"
        stmt = text(
            """
            SELECT id, document_id, chunk_index, content,
                   1 - (embedding <=> :vec::vector) AS score
            FROM document_chunks
            WHERE tenant_id = :tenant_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :vec::vector
            LIMIT :top_k
            """
        )
        result = await self.db.execute(
            stmt, {"vec": vector_str, "tenant_id": str(tenant_id), "top_k": top_k}
        )
        rows = result.all()
        return [
            {
                "chunk_id": row.id,
                "document_id": row.document_id,
                "chunk_index": row.chunk_index,
                "text_snippet": row.content[:300],
                "score": round(float(row.score), 4),
            }
            for row in rows
        ]

    async def hybrid_search(
        self, query: str, tenant_id: uuid.UUID, filters: dict[str, Any], top_k: int
    ) -> list[dict[str, Any]]:
        """Reciprocal Rank Fusion (RRF) of keyword + vector results."""
        keyword_results = await self.keyword_search(query, tenant_id, filters, top_k * 2)
        vector_results = await self.vector_search(query, tenant_id, filters, top_k * 2)

        rrf_k = 60
        scores: dict[str, float] = {}
        items: dict[str, dict[str, Any]] = {}

        for rank, item in enumerate(keyword_results):
            cid = str(item["chunk_id"])
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
            items[cid] = item

        for rank, item in enumerate(vector_results):
            cid = str(item["chunk_id"])
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
            items[cid] = item

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_k]
        return [{**items[cid], "score": round(scores[cid], 4)} for cid in sorted_ids]

    @staticmethod
    def build_citations(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Format results into citation objects."""
        return results
