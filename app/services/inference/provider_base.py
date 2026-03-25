"""Base inference provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseInferenceProvider(ABC):
    """Abstract base for all inference providers."""

    provider_name: str = "base"

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Generate a structured JSON response."""
        ...

    @abstractmethod
    async def summarize(self, text: str, system_prompt: str | None = None) -> str:
        """Produce a text summary."""
        ...

    @abstractmethod
    async def classify(
        self, text: str, categories: list[str], system_prompt: str | None = None
    ) -> dict[str, Any]:
        """Classify text into one of the given categories."""
        ...

    @abstractmethod
    async def explain(
        self, context: str, question: str, system_prompt: str | None = None
    ) -> str:
        """Generate an evidence-backed explanation."""
        ...
