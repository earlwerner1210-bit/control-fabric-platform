"""Application configuration using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    # ── Application ───────────────────────────────────────────────
    APP_NAME: str = "Control Fabric Platform"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["dev", "staging", "prod"] = "dev"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Database ──────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://fabric:fabric@localhost:5432/controlfabric"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # ── Redis ─────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Auth / Security ───────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60
    API_KEY_HEADER: str = "X-API-Key"

    # ── Temporal ──────────────────────────────────────────────────
    TEMPORAL_HOST: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "control-fabric"
    TEMPORAL_TASK_QUEUE: str = "control-fabric-queue"

    # ── Inference ─────────────────────────────────────────────────
    INFERENCE_PROVIDER: Literal["vllm", "openai", "mlx", "fake"] = "fake"
    VLLM_BASE_URL: str = "http://localhost:8001/v1"
    VLLM_MODEL: str = "default"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str = ""
    MLX_ENABLED: bool = False
    MLX_MODEL_PATH: str = ""

    # ── Embedding ─────────────────────────────────────────────────
    EMBEDDING_PROVIDER: Literal["openai", "local", "fake"] = "fake"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    # ── Storage ───────────────────────────────────────────────────
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_LOCAL_PATH: str = "./storage"
    S3_ENDPOINT: str = ""
    S3_BUCKET: str = "control-fabric"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"

    # ── Observability ─────────────────────────────────────────────
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_ENDPOINT: str = "http://localhost:4317"
    METRICS_ENABLED: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
