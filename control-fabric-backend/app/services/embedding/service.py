"""Embedding service -- pluggable providers for vector generation."""

from __future__ import annotations

import logging
import math
import random
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ── Provider interface ────────────────────────────────────────────────────


class EmbeddingProvider(ABC):
    """Abstract base for embedding providers."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return a list of embedding vectors, one per input text."""

    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of produced vectors."""


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic pseudo-random embeddings for dev/test."""

    def __init__(self, dim: int = 1536) -> None:
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            rng = random.Random(hash(text))
            vec = [rng.gauss(0, 1) for _ in range(self._dim)]
            # L2-normalise
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0:
                vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors

    def dimension(self) -> int:
        return self._dim


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Calls the OpenAI embeddings API."""

    def __init__(
        self, api_key: str, model: str = "text-embedding-3-small", dim: int = 1536
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dim = dim
        self._client = httpx.Client(
            base_url="https://api.openai.com/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.post(
            "/embeddings",
            json={"input": texts, "model": self._model},
        )
        resp.raise_for_status()
        data = resp.json()
        # Sort by index to guarantee order
        items = sorted(data["data"], key=lambda d: d["index"])
        return [item["embedding"] for item in items]

    def dimension(self) -> int:
        return self._dim


# ── Service ───────────────────────────────────────────────────────────────


class EmbeddingService:
    """High-level embedding operations used by the rest of the platform."""

    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self._provider = provider or self._get_provider()

    @staticmethod
    def _get_provider() -> EmbeddingProvider:
        """Factory: select a provider based on application settings."""
        settings = get_settings()
        if settings.EMBEDDING_PROVIDER == "openai":
            if not settings.OPENAI_API_KEY:
                raise RuntimeError("OPENAI_API_KEY is required for the OpenAI embedding provider")
            return OpenAIEmbeddingProvider(
                api_key=settings.OPENAI_API_KEY,
                model=settings.EMBEDDING_MODEL,
                dim=settings.EMBEDDING_DIMENSION,
            )
        # Default to fake
        return FakeEmbeddingProvider(dim=settings.EMBEDDING_DIMENSION)

    def get_provider(self) -> EmbeddingProvider:
        """Return the active embedding provider."""
        return self._provider

    # ── Core operations ───────────────────────────────────────────────────

    def embed_chunks(
        self,
        chunks: list[dict[str, Any]],
        model: str | None = None,
    ) -> list[list[float]]:
        """Embed a list of chunk dicts (each must have a ``text`` key)."""
        texts = [c["text"] for c in chunks]
        if not texts:
            return []
        vectors = self._provider.embed(texts)
        logger.info("embedding.embed_chunks: %d chunks -> %d vectors", len(texts), len(vectors))
        return vectors

    def embed_query(self, query: str, model: str | None = None) -> list[float]:
        """Embed a single query string and return the vector."""
        vectors = self._provider.embed([query])
        return vectors[0]

    # ── Similarity utilities ──────────────────────────────────────────────

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two equal-length vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def find_similar(
        self,
        query_vec: list[float],
        stored: list[tuple[Any, list[float]]],
        top_k: int = 5,
    ) -> list[tuple[Any, float]]:
        """Return the *top_k* most similar items from *stored*.

        *stored* is a list of ``(id_or_metadata, vector)`` tuples.
        Returns ``(id_or_metadata, similarity_score)`` sorted descending.
        """
        scored = [(item_id, self.cosine_similarity(query_vec, vec)) for item_id, vec in stored]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:top_k]


# Singleton
embedding_service = EmbeddingService()
