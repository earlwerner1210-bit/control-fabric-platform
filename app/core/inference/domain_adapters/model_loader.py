"""
Domain Model Loader

Loads fine-tuned LoRA adapters for domain SLMs.
Singleton per domain — adapters are loaded once and cached.

Falls back gracefully when MLX is not available or adapter not trained.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import mlx_lm

    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False


@dataclass
class LoadedModel:
    """A loaded domain model with its adapter."""

    domain: str
    base_model_id: str
    adapter_path: str
    model: object = None
    tokenizer: object = None
    is_loaded: bool = False
    is_dry_run: bool = False
    manifest: dict = field(default_factory=dict)


class DomainModelLoader:
    """
    Singleton loader for domain-specific fine-tuned models.

    Usage:
        loader = DomainModelLoader.instance()
        model = loader.load("telecom")
        if model.is_loaded:
            result = loader.generate(model, prompt)
    """

    _instance: DomainModelLoader | None = None
    _models: dict[str, LoadedModel] = {}

    @classmethod
    def instance(cls) -> DomainModelLoader:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None
        cls._models = {}

    def __init__(self) -> None:
        self._models: dict[str, LoadedModel] = {}
        self._base_dir = Path("slm/models")

    def load(self, domain: str) -> LoadedModel:
        """Load a domain model. Returns LoadedModel (check is_loaded)."""
        if domain in self._models:
            return self._models[domain]

        adapter_dir = self._base_dir / domain / "domain-lora"
        manifest_path = adapter_dir / "manifest.json"

        if not manifest_path.exists():
            logger.info("No fine-tuned model for domain %s", domain)
            model = LoadedModel(
                domain=domain,
                base_model_id="none",
                adapter_path="",
                is_loaded=False,
            )
            self._models[domain] = model
            return model

        manifest = json.loads(manifest_path.read_text())
        base_model_id = manifest.get("base_model", "unknown")
        is_dry_run = manifest.get("dry_run", False)

        if is_dry_run or not MLX_AVAILABLE:
            logger.info(
                "Domain model %s available but not loadable (dry_run=%s, mlx=%s)",
                domain,
                is_dry_run,
                MLX_AVAILABLE,
            )
            model = LoadedModel(
                domain=domain,
                base_model_id=base_model_id,
                adapter_path=str(adapter_dir),
                is_loaded=False,
                is_dry_run=is_dry_run,
                manifest=manifest,
            )
            self._models[domain] = model
            return model

        try:
            mlx_model, tokenizer = mlx_lm.load(
                base_model_id,
                adapter_path=str(adapter_dir),
            )
            model = LoadedModel(
                domain=domain,
                base_model_id=base_model_id,
                adapter_path=str(adapter_dir),
                model=mlx_model,
                tokenizer=tokenizer,
                is_loaded=True,
                manifest=manifest,
            )
            self._models[domain] = model
            logger.info("Loaded fine-tuned model for domain %s", domain)
            return model
        except Exception as e:
            logger.warning("Failed to load model for %s: %s", domain, e)
            model = LoadedModel(
                domain=domain,
                base_model_id=base_model_id,
                adapter_path=str(adapter_dir),
                is_loaded=False,
                manifest=manifest,
            )
            self._models[domain] = model
            return model

    def generate(
        self,
        loaded_model: LoadedModel,
        prompt: str,
        max_tokens: int = 512,
    ) -> str | None:
        """Generate text using a loaded model. Returns None if not available."""
        if not loaded_model.is_loaded or loaded_model.model is None:
            return None

        try:
            return mlx_lm.generate(
                loaded_model.model,
                loaded_model.tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error("Generation failed for %s: %s", loaded_model.domain, e)
            return None

    def is_available(self, domain: str) -> bool:
        """Check if a fine-tuned model is available for this domain."""
        if domain in self._models:
            return self._models[domain].is_loaded
        adapter_dir = self._base_dir / domain / "domain-lora"
        return (adapter_dir / "manifest.json").exists()

    def list_models(self) -> list[dict]:
        """List all loaded/attempted models."""
        return [
            {
                "domain": m.domain,
                "base_model": m.base_model_id,
                "is_loaded": m.is_loaded,
                "is_dry_run": m.is_dry_run,
                "adapter_path": m.adapter_path,
            }
            for m in self._models.values()
        ]
