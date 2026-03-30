"""Fake inference provider returning canned responses for tests."""

from __future__ import annotations

from typing import Any

from .base import BaseInferenceProvider


class FakeProvider(BaseInferenceProvider):
    """Returns deterministic canned responses for testing."""

    MODEL_NAME = "fake-model-v1"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        output = (
            '{"result": "fake generated output"}'
            if response_format == "json"
            else "Fake generated output."
        )
        return {
            "output": output,
            "model": self.MODEL_NAME,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    async def summarize(self, text: str, max_length: int = 200) -> dict[str, Any]:
        return {
            "summary": f"Summary of text ({len(text)} chars): {text[:50]}...",
            "model": self.MODEL_NAME,
        }

    async def classify(self, text: str, categories: list[str]) -> dict[str, Any]:
        return {
            "category": categories[0] if categories else "unknown",
            "confidence": 0.95,
            "model": self.MODEL_NAME,
        }

    async def explain(self, text: str, context: str | None = None) -> dict[str, Any]:
        return {
            "explanation": f"Explanation: {text[:100]}",
            "model": self.MODEL_NAME,
        }
