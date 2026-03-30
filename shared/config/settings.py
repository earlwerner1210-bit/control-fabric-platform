"""Application settings using pydantic-settings."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    dev = "dev"
    staging = "staging"
    prod = "prod"


class Settings(BaseSettings):
    """Central configuration sourced from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ───────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/control_fabric"
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── AI / LLM ──────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    MLX_ENABLED: bool = False

    # ── Auth ──────────────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    # ── Temporal ──────────────────────────────────────────────────────
    TEMPORAL_HOST: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"

    # ── S3 / Object Storage ───────────────────────────────────────────
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_BUCKET: str = "control-fabric"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""

    # ── Observability ─────────────────────────────────────────────────
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    ENVIRONMENT: Environment = Environment.dev

    @property
    def sync_database_url(self) -> str:
        """Return a synchronous driver URL (useful for Alembic migrations)."""
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg2").replace(
            "postgresql://", "postgresql+psycopg2://"
        )
