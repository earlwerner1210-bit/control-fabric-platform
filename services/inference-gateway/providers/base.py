"""Abstract base class for inference providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseInferenceProvider(ABC):
    """Interface that all inference providers must implement."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        """Generate a completion. Returns dict with 'output', 'model', 'usage'."""
        ...

    @abstractmethod
    async def summarize(self, text: str, max_length: int = 200) -> dict[str, Any]:
        """Summarize text. Returns dict with 'summary', 'model'."""
        ...

    @abstractmethod
    async def classify(self, text: str, categories: list[str]) -> dict[str, Any]:
        """Classify text into categories. Returns dict with 'category', 'confidence', 'model'."""
        ...

    @abstractmethod
    async def explain(self, text: str, context: str | None = None) -> dict[str, Any]:
        """Explain text. Returns dict with 'explanation', 'model'."""
        ...
