"""
Control Fabric Platform — Bounded Inference Engine
MLX Runner: Apple Silicon SLM Inference

The original product idea — SLM running entirely on Apple Silicon.
No cloud. No data egress. Zero external dependency.

Patent Reference: Layer 5, Bounded Reasoning Layer.

Author: Control Fabric Platform
Date: March 2026
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from models.domain_types import HypothesisType, ScopeParameters, TypedHypothesis

logger = logging.getLogger(__name__)

try:
    from mlx_lm import generate, load

    MLX_AVAILABLE = True
    logger.info("MLX available — Apple Silicon inference enabled")
except ImportError:
    MLX_AVAILABLE = False
    logger.warning("MLX not available — simulation mode active")


class ModelConfig:
    def __init__(
        self,
        model_id: str,
        model_path: str,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        top_p: float = 0.9,
        description: str = "",
    ) -> None:
        self.model_id = model_id
        self.model_path = model_path
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.description = description


DEFAULT_MODELS = {
    "llama-3-8b-4bit": ModelConfig(
        "llama-3-8b-4bit",
        "mlx-community/Meta-Llama-3-8B-Instruct-4bit",
        description="Llama 3 8B 4-bit",
    ),
    "mistral-7b-4bit": ModelConfig(
        "mistral-7b-4bit",
        "mlx-community/Mistral-7B-Instruct-v0.3-4bit",
        description="Mistral 7B 4-bit",
    ),
    "phi-3-mini": ModelConfig(
        "phi-3-mini",
        "mlx-community/Phi-3-mini-4k-instruct-4bit",
        max_tokens=512,
        description="Phi-3 Mini — fastest",
    ),
}

SYSTEM_PROMPT = """You are a governance analysis assistant in a Control Fabric Platform.
CRITICAL CONSTRAINTS:
1. Respond with valid JSON ONLY — no prose, no markdown
2. Output MUST conform to TypedHypothesis schema
3. NEVER suggest executable actions or system commands
4. ONLY reference control objects provided in your context
5. is_executable MUST always be false
You generate structured hypotheses for deterministic review. You are NOT an action executor."""


class MLXRunner:
    """Apple Silicon SLM inference runner — zero cloud dependency."""

    def __init__(
        self, model_config: ModelConfig | None = None, simulation_mode: bool = False
    ) -> None:
        self._config = model_config or DEFAULT_MODELS["phi-3-mini"]
        self._simulation_mode = simulation_mode or not MLX_AVAILABLE
        self._model: Any = None
        self._tokenizer: Any = None
        if not self._simulation_mode:
            self._load_model()

    def _load_model(self) -> None:
        try:
            self._model, self._tokenizer = load(self._config.model_path)
            logger.info("Model loaded: %s", self._config.model_id)
        except Exception as e:
            logger.error("Model load failed: %s — falling back to simulation", e)
            self._simulation_mode = True

    def infer(
        self,
        scope: ScopeParameters,
        sanitised_context: dict[str, Any],
        hypothesis_type: HypothesisType,
        session_id: str,
    ) -> tuple[TypedHypothesis, int]:
        start_ms = int(time.time() * 1000)
        if self._simulation_mode:
            raw_output = self._simulate(hypothesis_type, scope, session_id)
        else:
            raw_output = self._run_mlx(scope, sanitised_context, hypothesis_type, session_id)
        duration_ms = int(time.time() * 1000) - start_ms
        return self._parse(raw_output, scope), duration_ms

    def _run_mlx(
        self,
        scope: ScopeParameters,
        sanitised_context: dict[str, Any],
        hypothesis_type: HypothesisType,
        session_id: str,
    ) -> str:
        user_prompt = f"Session: {session_id}\nType: {hypothesis_type.value}\nScope: {scope.scope_hash}\nContext: {json.dumps(sanitised_context, default=str)}\nGenerate {hypothesis_type.value} hypothesis as JSON."
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        formatted = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return generate(
            model=self._model,
            tokenizer=self._tokenizer,
            prompt=formatted,
            max_tokens=self._config.max_tokens,
            temp=self._config.temperature,
            verbose=False,
        )

    def _simulate(
        self, hypothesis_type: HypothesisType, scope: ScopeParameters, session_id: str
    ) -> str:
        time.sleep(0.05)
        object_ids = scope.allowed_control_object_ids[:3]
        return json.dumps(
            {
                "hypothesis_id": str(uuid.uuid4()),
                "hypothesis_type": hypothesis_type.value,
                "title": f"Simulated {hypothesis_type.value} for session {session_id[:8]}",
                "findings": [f"Control object {oid} requires review" for oid in object_ids],
                "affected_control_object_ids": object_ids,
                "confidence_score": 0.78,
                "evidence_references": [f"evidence-{oid}" for oid in object_ids],
                "reasoning_trace": [
                    "Analysed objects in scope",
                    "Identified relationships",
                    f"Applied {hypothesis_type.value} framework",
                    "Generated findings",
                ],
                "scope_hash_used": scope.scope_hash,
                "model_id": f"simulation:{self._config.model_id}",
                "is_executable": False,
            }
        )

    def _parse(self, raw_output: str, scope: ScopeParameters) -> TypedHypothesis:
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Model output is not valid JSON: {e}") from e
        data["scope_hash_used"] = scope.scope_hash
        data["is_executable"] = False
        try:
            return TypedHypothesis(**data)
        except Exception as e:
            raise ValueError(f"Output does not conform to TypedHypothesis schema: {e}") from e

    @property
    def model_id(self) -> str:
        return self._config.model_id

    @property
    def is_simulation(self) -> bool:
        return self._simulation_mode
