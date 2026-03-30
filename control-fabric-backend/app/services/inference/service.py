"""Inference gateway service -- pluggable LLM providers."""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.inference import InferenceResponse

logger = logging.getLogger(__name__)


# ── Provider interface ────────────────────────────────────────────────────


class InferenceProvider(ABC):
    """Abstract base for inference providers."""

    @abstractmethod
    def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a prompt to the underlying model.

        Must return a dict with at least:
        ``content``, ``model``, ``input_tokens``, ``output_tokens``.
        """


class VLLMProvider(InferenceProvider):
    """Calls a vLLM (or any OpenAI-compatible) inference server via HTTP."""

    def __init__(self, base_url: str, model: str, api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=120.0,
        )

    def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": kwargs.get("model") or self._model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.0),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        response_format = kwargs.get("response_format")
        if response_format:
            body["response_format"] = response_format

        resp = self._client.post("/v1/chat/completions", json=body)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})
        return {
            "content": choice["message"]["content"],
            "model": data.get("model", body["model"]),
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }


class MLXProvider(InferenceProvider):
    """Placeholder for local MLX-based inference (Apple Silicon)."""

    def __init__(self, model_path: str) -> None:
        self._model_path = model_path

    def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        # In production, load an MLX model and run inference locally.
        raise NotImplementedError(
            "MLX inference is not yet implemented. Set INFERENCE_PROVIDER=vllm or fake."
        )


class FakeProvider(InferenceProvider):
    """Returns canned responses for development and testing."""

    _CANNED: dict[str, str] = {
        "default": json.dumps(
            {
                "summary": "This is a stub response from FakeProvider.",
                "items": [],
                "confidence": 0.5,
            }
        ),
        "contract": json.dumps(
            {
                "contract_summary": "Master Service Agreement for managed network services.",
                "obligations": [
                    {"label": "Uptime SLA", "target": "99.9%", "penalty": "2% monthly credit"}
                ],
                "penalty_clauses": [
                    {"label": "Late delivery penalty", "amount": "1% per day", "cap": "10%"}
                ],
            }
        ),
        "margin": json.dumps(
            {
                "verdict": "under_recovery",
                "leakage_drivers": ["Unbacked labour charges"],
                "recovery_recommendations": ["Negotiate rate card amendment"],
            }
        ),
    }

    def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        # Pick a canned response based on keywords in the prompt
        lower = prompt.lower()
        if "contract" in lower:
            content = self._CANNED["contract"]
        elif "margin" in lower or "reconcil" in lower:
            content = self._CANNED["margin"]
        else:
            content = self._CANNED["default"]

        return {
            "content": content,
            "model": "fake-model",
            "input_tokens": len(prompt.split()),
            "output_tokens": len(content.split()),
        }


# ── Gateway ───────────────────────────────────────────────────────────────


class InferenceGateway:
    """Central entry point for all LLM inference calls in the platform."""

    def __init__(self, provider: InferenceProvider | None = None) -> None:
        self._provider = provider or self.get_provider()
        self._model_runs: list[dict[str, Any]] = []

    @staticmethod
    def get_provider() -> InferenceProvider:
        """Factory: select provider based on application settings."""
        settings = get_settings()
        if settings.INFERENCE_PROVIDER == "vllm":
            return VLLMProvider(
                base_url=settings.VLLM_BASE_URL,
                model=settings.VLLM_MODEL,
                api_key=settings.OPENAI_API_KEY,
            )
        if settings.INFERENCE_PROVIDER == "mlx":
            return MLXProvider(model_path=settings.MLX_MODEL_PATH)
        return FakeProvider()

    def call(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: dict[str, Any] | None = None,
    ) -> InferenceResponse:
        """Send a prompt through the active provider and return a structured response."""
        start = time.perf_counter()

        raw = self._provider.call(
            prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

        latency_ms = (time.perf_counter() - start) * 1000

        response = InferenceResponse(
            content=raw["content"],
            model=raw.get("model", model or "unknown"),
            input_tokens=raw.get("input_tokens", 0),
            output_tokens=raw.get("output_tokens", 0),
            latency_ms=round(latency_ms, 2),
        )

        self.record_model_run(
            provider=type(self._provider).__name__,
            model=response.model,
            operation="inference",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
        )

        logger.info(
            "inference.call: model=%s tokens_in=%d tokens_out=%d latency=%.1fms",
            response.model,
            response.input_tokens,
            response.output_tokens,
            response.latency_ms,
        )
        return response

    def record_model_run(
        self,
        provider: str,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        case_id: str | None = None,
    ) -> None:
        """Record metadata about an inference call for audit / cost tracking."""
        run = {
            "provider": provider,
            "model": model,
            "operation": operation,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "case_id": case_id,
            "timestamp": time.time(),
        }
        self._model_runs.append(run)
        logger.debug("inference.record_model_run: %s", run)


# Singleton
inference_gateway = InferenceGateway()
