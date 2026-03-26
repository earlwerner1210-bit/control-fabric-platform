"""Retrieval service -- semantic and hybrid search over embedded chunks."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.services.embedding.service import EmbeddingService, embedding_service

logger = logging.getLogger(__name__)


@dataclass
class ChunkResult:
    """A single search result from the retrieval layer."""

    chunk_id: str
    document_id: UUID
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class _ChunkStore:
    """In-memory vector store stub -- replaced by pgvector in production."""

    def __init__(self) -> None:
        self._chunks: list[dict[str, Any]] = []

    def upsert(self, chunk: dict[str, Any]) -> None:
        self._chunks.append(chunk)

    def all_for_tenant(self, tenant_id: UUID) -> list[dict[str, Any]]:
        return [c for c in self._chunks if c.get("tenant_id") == tenant_id]

    def all_for_document(self, document_id: UUID) -> list[dict[str, Any]]:
        return [c for c in self._chunks if c.get("document_id") == document_id]


class RetrievalService:
    """Provides semantic and hybrid retrieval over embedded document chunks."""

    def __init__(
        self,
        embedding_svc: EmbeddingService | None = None,
    ) -> None:
        self._embedding = embedding_svc or embedding_service
        self._store = _ChunkStore()

    # ── Index management (in-memory stub) ─────────────────────────────────

    def index_chunks(
        self,
        tenant_id: UUID,
        document_id: UUID,
        chunks: list[dict[str, Any]],
        vectors: list[list[float]],
    ) -> int:
        """Store chunks + vectors for later retrieval."""
        for chunk, vec in zip(chunks, vectors):
            self._store.upsert(
                {
                    "chunk_id": chunk["id"],
                    "document_id": document_id,
                    "tenant_id": tenant_id,
                    "text": chunk["text"],
                    "vector": vec,
                    "metadata": chunk.get("metadata", {}),
                }
            )
        logger.info(
            "retrieval.index: tenant=%s doc=%s chunks=%d", tenant_id, document_id, len(chunks)
        )
        return len(chunks)

    # ── Query ─────────────────────────────────────────────────────────────

    def retrieve_relevant(
        self,
        tenant_id: UUID,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[ChunkResult]:
        """Semantic search across all chunks for *tenant_id*."""
        query_vec = self._embedding.embed_query(query)
        candidates = self._store.all_for_tenant(tenant_id)

        if filters:
            for key, value in filters.items():
                candidates = [c for c in candidates if c.get("metadata", {}).get(key) == value]

        if not candidates:
            return []

        stored = [(c, c["vector"]) for c in candidates]
        top = self._embedding.find_similar(query_vec, stored, top_k=top_k)
        return [
            ChunkResult(
                chunk_id=c["chunk_id"],
                document_id=c["document_id"],
                text=c["text"],
                score=score,
                metadata=c.get("metadata", {}),
            )
            for c, score in top
        ]

    def retrieve_by_document(
        self,
        document_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> list[ChunkResult]:
        """Semantic search scoped to a single document."""
        query_vec = self._embedding.embed_query(query)
        candidates = self._store.all_for_document(document_id)
        if not candidates:
            return []

        stored = [(c, c["vector"]) for c in candidates]
        top = self._embedding.find_similar(query_vec, stored, top_k=top_k)
        return [
            ChunkResult(
                chunk_id=c["chunk_id"],
                document_id=c["document_id"],
                text=c["text"],
                score=score,
                metadata=c.get("metadata", {}),
            )
            for c, score in top
        ]

    def hybrid_search(
        self,
        tenant_id: UUID,
        query: str,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7,
        top_k: int = 5,
    ) -> list[ChunkResult]:
        """Combine keyword (BM25-like) and semantic similarity scores.

        The keyword component is a simple term-overlap heuristic; in production
        this is replaced by a proper full-text search index (tsvector / Typesense).
        """
        query_vec = self._embedding.embed_query(query)
        candidates = self._store.all_for_tenant(tenant_id)
        if not candidates:
            return []

        query_terms = set(query.lower().split())

        scored: list[tuple[dict[str, Any], float]] = []
        for chunk in candidates:
            # Semantic score
            sem_score = self._embedding.cosine_similarity(query_vec, chunk["vector"])

            # Keyword score (simple Jaccard overlap)
            chunk_terms = set(chunk["text"].lower().split())
            overlap = len(query_terms & chunk_terms)
            kw_score = overlap / max(len(query_terms | chunk_terms), 1)

            combined = semantic_weight * sem_score + keyword_weight * kw_score
            scored.append((chunk, combined))

        scored.sort(key=lambda t: t[1], reverse=True)

        return [
            ChunkResult(
                chunk_id=c["chunk_id"],
                document_id=c["document_id"],
                text=c["text"],
                score=score,
                metadata=c.get("metadata", {}),
            )
            for c, score in scored[:top_k]
        ]


# Singleton
retrieval_service = RetrievalService()
