"""Embedding generation service with provider abstraction."""

from __future__ import annotations

import uuid
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import DocumentChunk

logger = get_logger("embedding")


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddingProvider:
    """OpenAI-compatible embedding provider."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                json={"input": texts, "model": self.model},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]


class FakeEmbeddingProvider:
    """Returns deterministic fake embeddings for testing."""

    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib

        results = []
        for text in texts:
            h = hashlib.md5(text.encode()).hexdigest()
            seed_val = int(h[:8], 16)
            vec = [(seed_val * (i + 1) % 1000) / 1000.0 - 0.5 for i in range(self.dimension)]
            results.append(vec)
        return results


def get_embedding_provider() -> EmbeddingProvider:
    """Resolve the configured embedding provider.

    Supports ``openai``, ``local`` (self-hosted HTTP endpoint), and
    ``fake`` (deterministic vectors for testing).
    """
    settings = get_settings()
    if settings.EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL,
        )
    if settings.EMBEDDING_PROVIDER == "local":
        return LocalEmbeddingProvider(
            base_url=settings.VLLM_BASE_URL,
            model=settings.EMBEDDING_MODEL,
        )
    return FakeEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)


class LocalEmbeddingProvider:
    """Local / self-hosted embedding provider (e.g. sentence-transformers via HTTP)."""

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                json={"input": texts, "model": self.model},
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]


class EmbeddingService:
    """Embedding generation with provider abstraction, batching, and similarity utilities."""

    DEFAULT_BATCH_SIZE: int = 50

    def __init__(
        self,
        db: AsyncSession,
        provider: EmbeddingProvider | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.db = db
        self.provider = provider or get_embedding_provider()
        self.batch_size = batch_size or self.DEFAULT_BATCH_SIZE

    # ── Document-chunk embedding (original) ───────────────────────

    async def embed_document_chunks(self, document_id: uuid.UUID, tenant_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id, DocumentChunk.tenant_id == tenant_id)
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = list(result.scalars().all())
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        all_embeddings = await self.embed_chunks(texts)
        for chunk, emb in zip(chunks, all_embeddings):
            chunk.embedding = emb

        await self.db.flush()
        logger.info("chunks_embedded", document_id=str(document_id), count=len(all_embeddings))
        return len(all_embeddings)

    # ── Batch chunk embedding ─────────────────────────────────────

    async def embed_chunks(
        self,
        chunks: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Embed a list of text chunks, batched by ``self.batch_size``.

        *model* is accepted for interface symmetry but the underlying
        provider's model is used (provider is selected at init time).
        Returns one embedding vector per input chunk.
        """
        all_embeddings: list[list[float]] = []
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            batch_embeddings = await self.provider.embed(batch)
            all_embeddings.extend(batch_embeddings)
        return all_embeddings

    # ── Single-query embedding ────────────────────────────────────

    async def embed_query(
        self,
        query: str,
        model: str | None = None,
    ) -> list[float]:
        """Embed a single query string and return its vector."""
        results = await self.provider.embed([query])
        return results[0]

    # ── Similarity utilities ──────────────────────────────────────

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two equal-length vectors.

        Returns a value in [-1, 1].  Returns 0.0 when either vector has
        zero magnitude.
        """
        import math

        if len(a) != len(b):
            raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0
        return dot / (mag_a * mag_b)

    @staticmethod
    def find_similar_chunks(
        query_embedding: list[float],
        stored_embeddings: list[list[float]],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """Return the *top_k* most similar embeddings as ``(index, score)`` pairs.

        Uses cosine similarity.  Results are sorted descending by score.
        """
        import math

        scores: list[tuple[int, float]] = []
        mag_q = math.sqrt(sum(x * x for x in query_embedding))
        if mag_q == 0.0:
            return []

        for idx, emb in enumerate(stored_embeddings):
            dot = sum(x * y for x, y in zip(query_embedding, emb))
            mag_e = math.sqrt(sum(x * x for x in emb))
            if mag_e == 0.0:
                continue
            score = dot / (mag_q * mag_e)
            scores.append((idx, score))

        scores.sort(key=lambda t: t[1], reverse=True)
        return scores[:top_k]
