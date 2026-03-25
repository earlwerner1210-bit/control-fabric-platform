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
    settings = get_settings()
    if settings.EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.EMBEDDING_MODEL,
        )
    return FakeEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)


class EmbeddingService:
    def __init__(self, db: AsyncSession, provider: EmbeddingProvider | None = None) -> None:
        self.db = db
        self.provider = provider or get_embedding_provider()

    async def embed_document_chunks(
        self, document_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> int:
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id, DocumentChunk.tenant_id == tenant_id)
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = list(result.scalars().all())
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        # Batch in groups of 50
        batch_size = 50
        embedded = 0
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = await self.provider.embed(batch)
            for chunk, emb in zip(chunks[i : i + batch_size], embeddings):
                chunk.embedding = emb
                embedded += 1

        await self.db.flush()
        logger.info("chunks_embedded", document_id=str(document_id), count=embedded)
        return embedded
