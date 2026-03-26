"""Embedding service business logic."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.models import DocumentChunk
from shared.telemetry.logging import get_logger

logger = get_logger("embedding_service")


class EmbeddingProvider:
    """OpenAI-compatible embedding provider abstraction."""

    def __init__(
        self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1"
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Call an OpenAI-compatible embeddings endpoint."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"input": texts, "model": self.model},
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]


class EmbeddingService:
    """Generates and persists embeddings for document chunks."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        settings = get_settings()
        self.model_name = settings.EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
        self.provider = EmbeddingProvider(api_key=settings.OPENAI_API_KEY, model=self.model_name)

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        vectors = await self.provider.embed([text])
        return vectors[0]

    async def batch_embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return await self.provider.embed(texts)

    async def persist_embeddings(
        self, chunk_ids: list[uuid.UUID], vectors: list[list[float]], tenant_id: uuid.UUID
    ) -> None:
        """Store generated embeddings on their corresponding chunks."""
        for chunk_id, vector in zip(chunk_ids, vectors):
            result = await self.db.execute(
                select(DocumentChunk).where(
                    DocumentChunk.id == chunk_id,
                    DocumentChunk.tenant_id == tenant_id,
                )
            )
            chunk = result.scalar_one_or_none()
            if chunk:
                chunk.embedding = vector
        await self.db.flush()
        logger.info("Persisted embeddings for %d chunks", len(chunk_ids))

    async def generate_and_persist(
        self, chunk_id: uuid.UUID, text: str, tenant_id: uuid.UUID
    ) -> list[float]:
        """Generate and persist a single embedding."""
        vector = await self.generate_embedding(text)
        await self.persist_embeddings([chunk_id], [vector], tenant_id)
        return vector

    async def batch_generate_and_persist(
        self, items: list[dict], tenant_id: uuid.UUID
    ) -> list[list[float]]:
        """Generate and persist embeddings for a batch of chunks."""
        texts = [item["text"] for item in items]
        chunk_ids = [item["chunk_id"] for item in items]
        vectors = await self.batch_embed(texts)
        await self.persist_embeddings(chunk_ids, vectors, tenant_id)
        return vectors
