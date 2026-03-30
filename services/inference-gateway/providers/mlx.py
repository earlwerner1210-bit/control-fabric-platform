"""MLX inference provider (placeholder)."""

from __future__ import annotations

from typing import Any

from .base import BaseInferenceProvider


class MLXProvider(BaseInferenceProvider):
    """Placeholder provider for Apple MLX inference.

    Not yet implemented -- raises NotImplementedError for all methods.
    """

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("MLX provider is not yet implemented")

    async def summarize(self, text: str, max_length: int = 200) -> dict[str, Any]:
        raise NotImplementedError("MLX provider is not yet implemented")

    async def classify(self, text: str, categories: list[str]) -> dict[str, Any]:
        raise NotImplementedError("MLX provider is not yet implemented")

    async def explain(self, text: str, context: str | None = None) -> dict[str, Any]:
        raise NotImplementedError("MLX provider is not yet implemented")
