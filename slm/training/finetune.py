"""
MLX LoRA Fine-Tuning Harness

Fine-tunes a base SLM using LoRA adapters on Apple Silicon via MLX.
Falls back gracefully when MLX is not available (e.g., Linux CI).

Architecture:
  - Base model: any HuggingFace-compatible model (e.g., Qwen2-0.5B, Phi-3-mini)
  - LoRA rank: configurable (default 16)
  - Training data: JSONL from SyntheticScenarioGenerator
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import mlx.core as mx  # noqa: F401
    import mlx_lm

    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False
    logger.info("MLX not available — fine-tuning will run in dry-run mode")


@dataclass
class LoRAConfig:
    """LoRA fine-tuning configuration."""

    base_model: str = "mlx-community/Qwen2-0.5B-Instruct-4bit"
    lora_rank: int = 16
    lora_alpha: float = 32.0
    lora_dropout: float = 0.05
    learning_rate: float = 1e-4
    batch_size: int = 4
    num_epochs: int = 3
    max_seq_length: int = 512
    warmup_steps: int = 100
    save_steps: int = 500
    eval_steps: int = 250
    gradient_accumulation_steps: int = 4
    output_dir: str = "slm/models"
    adapter_name: str = "domain-lora"


@dataclass
class FinetuneResult:
    """Result of a fine-tuning run."""

    success: bool
    model_path: str = ""
    adapter_path: str = ""
    training_loss: float = 0.0
    eval_loss: float = 0.0
    num_examples: int = 0
    training_time_seconds: float = 0.0
    config: dict = field(default_factory=dict)
    error: str = ""
    dry_run: bool = False

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "model_path": self.model_path,
            "adapter_path": self.adapter_path,
            "training_loss": self.training_loss,
            "eval_loss": self.eval_loss,
            "num_examples": self.num_examples,
            "training_time_seconds": self.training_time_seconds,
            "config": self.config,
            "error": self.error,
            "dry_run": self.dry_run,
        }


class MLXLoRAFineTuner:
    """
    Fine-tunes a base model with LoRA adapters using MLX.

    Falls back to dry-run mode when MLX is not available.
    """

    def __init__(
        self,
        config: LoRAConfig | None = None,
        domain: str = "telecom",
        training_data_path: str | None = None,
    ) -> None:
        self.config = config or LoRAConfig()
        self.domain = domain
        self.training_data_path = training_data_path or (f"slm/training/data/{domain}_train.jsonl")
        self.output_dir = Path(self.config.output_dir) / domain
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def train(self, dry_run: bool = False) -> FinetuneResult:
        """Run fine-tuning. Returns FinetuneResult."""
        if dry_run or not MLX_AVAILABLE:
            return self._dry_run()

        return self._train_mlx()

    def _dry_run(self) -> FinetuneResult:
        """Simulate training without MLX."""
        logger.info("Fine-tuning dry run for domain %s", self.domain)

        training_file = Path(self.training_data_path)
        num_examples = 0
        if training_file.exists():
            with open(training_file) as f:
                num_examples = sum(1 for _ in f)

        adapter_path = str(self.output_dir / self.config.adapter_name)
        os.makedirs(adapter_path, exist_ok=True)

        manifest = {
            "domain": self.domain,
            "base_model": self.config.base_model,
            "lora_rank": self.config.lora_rank,
            "num_examples": num_examples,
            "dry_run": True,
            "created_at": datetime.now(UTC).isoformat(),
        }
        manifest_path = Path(adapter_path) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        logger.info("Dry run complete: %d examples, adapter at %s", num_examples, adapter_path)
        return FinetuneResult(
            success=True,
            model_path=self.config.base_model,
            adapter_path=adapter_path,
            training_loss=0.0,
            eval_loss=0.0,
            num_examples=num_examples,
            training_time_seconds=0.0,
            config=self._config_dict(),
            dry_run=True,
        )

    def _train_mlx(self) -> FinetuneResult:
        """Run actual MLX LoRA fine-tuning."""
        start_time = datetime.now(UTC)
        try:
            logger.info(
                "Starting MLX LoRA fine-tuning: model=%s, rank=%d",
                self.config.base_model,
                self.config.lora_rank,
            )

            model, tokenizer = mlx_lm.load(self.config.base_model)

            training_file = Path(self.training_data_path)
            if not training_file.exists():
                return FinetuneResult(
                    success=False,
                    error=f"Training data not found: {training_file}",
                    config=self._config_dict(),
                )

            adapter_path = str(self.output_dir / self.config.adapter_name)

            training_args = {
                "model": model,
                "tokenizer": tokenizer,
                "train_dataset": str(training_file),
                "adapter_path": adapter_path,
                "lora_rank": self.config.lora_rank,
                "num_epochs": self.config.num_epochs,
                "batch_size": self.config.batch_size,
                "learning_rate": self.config.learning_rate,
            }

            if hasattr(mlx_lm, "lora"):
                mlx_lm.lora(**training_args)
            else:
                logger.warning("mlx_lm.lora not found — saving adapter manifest only")
                os.makedirs(adapter_path, exist_ok=True)

            elapsed = (datetime.now(UTC) - start_time).total_seconds()

            manifest = {
                "domain": self.domain,
                "base_model": self.config.base_model,
                "lora_rank": self.config.lora_rank,
                "training_time_seconds": elapsed,
                "created_at": datetime.now(UTC).isoformat(),
            }
            manifest_path = Path(adapter_path) / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))

            return FinetuneResult(
                success=True,
                model_path=self.config.base_model,
                adapter_path=adapter_path,
                training_time_seconds=elapsed,
                config=self._config_dict(),
            )

        except Exception as e:
            logger.error("MLX fine-tuning failed: %s", e)
            return FinetuneResult(
                success=False,
                error=str(e),
                config=self._config_dict(),
            )

    def _config_dict(self) -> dict:
        return {
            "base_model": self.config.base_model,
            "lora_rank": self.config.lora_rank,
            "lora_alpha": self.config.lora_alpha,
            "learning_rate": self.config.learning_rate,
            "batch_size": self.config.batch_size,
            "num_epochs": self.config.num_epochs,
            "max_seq_length": self.config.max_seq_length,
            "domain": self.domain,
        }
