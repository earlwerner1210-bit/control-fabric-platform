"""Inference gateway -- abstracts LLM providers behind a unified interface."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InferenceRequest:
    """Request to the inference gateway."""

    prompt: str
    system_prompt: str | None = None
    model: str = "gpt-4"
    provider: str = "openai"
    temperature: float = 0.0
    max_tokens: int = 2048
    response_format: str | None = None  # "json" for structured output


@dataclass
class InferenceResponse:
    """Response from the inference gateway."""

    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any] | None:
        """Parse content as JSON, return None if not valid JSON."""
        try:
            return json.loads(self.content)
        except (json.JSONDecodeError, TypeError):
            return None


class InferenceProvider(ABC):
    """Abstract base class for inference providers."""

    @abstractmethod
    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Generate a completion."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        ...


class FakeProvider(InferenceProvider):
    """A fake provider for testing that returns deterministic responses.

    Supports structured JSON output via response_format="json".
    """

    def __init__(
        self,
        default_response: str = '{"result": "ok"}',
        responses: dict[str, str] | None = None,
        latency_ms: int = 50,
    ) -> None:
        self._default_response = default_response
        self._responses = responses or {}
        self._latency_ms = latency_ms
        self._call_count = 0
        self._last_request: InferenceRequest | None = None

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Return a predetermined response."""
        self._call_count += 1
        self._last_request = request

        # Look up response by model or prompt keyword
        content = self._default_response
        for key, response in self._responses.items():
            if key in request.prompt or key == request.model:
                content = response
                break

        # Simulate token counts
        input_tokens = len(request.prompt.split())
        output_tokens = len(content.split())

        return InferenceResponse(
            content=content,
            model=request.model,
            provider=self.provider_name(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=self._latency_ms,
        )

    def provider_name(self) -> str:
        return "fake"

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def last_request(self) -> InferenceRequest | None:
        return self._last_request


class InferenceGateway:
    """Unified gateway for routing inference requests to providers."""

    def __init__(self) -> None:
        self._providers: dict[str, InferenceProvider] = {}

    def register_provider(self, name: str, provider: InferenceProvider) -> None:
        """Register a provider by name."""
        self._providers[name] = provider

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Route request to the appropriate provider."""
        provider = self._providers.get(request.provider)
        if provider is None:
            raise ValueError(f"Unknown provider: {request.provider}")

        start = time.perf_counter()
        response = await provider.generate(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.latency_ms = max(response.latency_ms, elapsed_ms)
        return response

    async def generate_structured(self, request: InferenceRequest) -> dict[str, Any]:
        """Generate a response and parse as JSON.

        Raises ValueError if the response is not valid JSON.
        """
        request.response_format = "json"
        response = await self.generate(request)
        parsed = response.to_json()
        if parsed is None:
            raise ValueError(f"Response is not valid JSON: {response.content[:200]}")
        return parsed
