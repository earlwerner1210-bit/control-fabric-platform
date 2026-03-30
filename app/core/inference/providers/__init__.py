"""Inference provider registry."""

from __future__ import annotations

from shared.config import get_settings

from .base import BaseInferenceProvider
from .fake import FakeProvider
from .mlx import MLXProvider
from .vllm import VLLMProvider


def get_provider(name: str | None = None) -> BaseInferenceProvider:
    """Factory function returning the requested provider instance."""
    settings = get_settings()

    if name == "fake" or name == "test":
        return FakeProvider()
    if name == "mlx":
        return MLXProvider()
    if name == "vllm" or name is None:
        return VLLMProvider(
            base_url=settings.VLLM_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
        )

    raise ValueError(f"Unknown inference provider: {name}")


__all__ = ["BaseInferenceProvider", "FakeProvider", "MLXProvider", "VLLMProvider", "get_provider"]
