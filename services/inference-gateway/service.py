"""Inference gateway business logic."""

from __future__ import annotations

from typing import Any

from shared.telemetry.logging import get_logger

from .providers import get_provider
from .providers.base import BaseInferenceProvider

logger = get_logger("inference_gateway")


class InferenceGateway:
    """Routes inference requests to the configured provider."""

    def __init__(self, provider_name: str | None = None) -> None:
        self.provider: BaseInferenceProvider = get_provider(provider_name)

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        """Generate a structured (or freeform) completion."""
        result = await self.provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )
        logger.info(
            "Generated completion: model=%s, tokens=%s",
            result.get("model"),
            result.get("usage", {}).get("total_tokens"),
        )
        return result

    async def summarize(self, text: str, max_length: int = 200) -> dict[str, Any]:
        """Summarize the given text."""
        result = await self.provider.summarize(text, max_length)
        logger.info("Summarized text: model=%s", result.get("model"))
        return result

    async def classify(self, text: str, categories: list[str]) -> dict[str, Any]:
        """Classify text into one of the given categories."""
        result = await self.provider.classify(text, categories)
        logger.info(
            "Classified text as %s (%.2f): model=%s",
            result.get("category"),
            result.get("confidence", 0),
            result.get("model"),
        )
        return result

    async def explain(self, text: str, context: str | None = None) -> dict[str, Any]:
        """Explain the given text."""
        result = await self.provider.explain(text, context)
        logger.info("Explained text: model=%s", result.get("model"))
        return result
