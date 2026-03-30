"""Fake inference provider for testing and local development."""

from __future__ import annotations

from typing import Any

from app.services.inference.provider_base import BaseInferenceProvider


class FakeProvider(BaseInferenceProvider):
    """Returns deterministic canned responses for testing."""

    provider_name = "fake"

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        return {
            "result": "fake_structured_output",
            "confidence": 0.95,
            "reasoning": "This is a deterministic fake response for testing purposes.",
            "evidence": ["Based on provided context"],
            "recommendations": ["Review with domain expert"],
        }

    async def summarize(self, text: str, system_prompt: str | None = None) -> str:
        word_count = len(text.split())
        return f"Summary of {word_count}-word document: Key points extracted from the provided content for analysis."

    async def classify(
        self, text: str, categories: list[str], system_prompt: str | None = None
    ) -> dict[str, Any]:
        # Return first category with high confidence for deterministic testing
        return {
            "category": categories[0] if categories else "unknown",
            "confidence": 0.92,
        }

    async def explain(self, context: str, question: str, system_prompt: str | None = None) -> str:
        return (
            f"Based on the provided context, the analysis indicates: "
            f"The question '{question[:50]}...' can be addressed by examining the evidence. "
            f"Key factors include the data points present in the context material. "
            f"Recommendation: validate against business rules before finalizing."
        )
