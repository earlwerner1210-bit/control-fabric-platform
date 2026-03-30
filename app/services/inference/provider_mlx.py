"""MLX local inference provider – placeholder for future implementation."""

from __future__ import annotations

from typing import Any

from app.services.inference.provider_base import BaseInferenceProvider


class MLXProvider(BaseInferenceProvider):
    """Placeholder MLX provider. Structured for future local inference integration."""

    provider_name = "mlx"

    def __init__(self, model_path: str = "") -> None:
        self.model_path = model_path
        # TODO: Load MLX model when implemented
        # from mlx_lm import load, generate
        # self.model, self.tokenizer = load(model_path)

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: dict | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "MLX provider not yet implemented. Set INFERENCE_PROVIDER=vllm or fake."
        )

    async def summarize(self, text: str, system_prompt: str | None = None) -> str:
        raise NotImplementedError("MLX provider not yet implemented.")

    async def classify(
        self, text: str, categories: list[str], system_prompt: str | None = None
    ) -> dict[str, Any]:
        raise NotImplementedError("MLX provider not yet implemented.")

    async def explain(self, context: str, question: str, system_prompt: str | None = None) -> str:
        raise NotImplementedError("MLX provider not yet implemented.")
