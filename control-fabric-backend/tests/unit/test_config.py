"""Unit tests for application configuration Settings."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.core.config import Settings


class TestSettings:
    def test_default_app_name(self):
        settings = Settings()
        assert settings.APP_NAME == "control-fabric-backend"

    def test_default_version(self):
        settings = Settings()
        assert settings.APP_VERSION == "0.1.0"

    def test_default_environment(self):
        settings = Settings()
        assert settings.ENVIRONMENT in ("dev", "staging", "prod")

    def test_default_database_url(self):
        settings = Settings()
        assert "postgresql" in settings.DATABASE_URL

    def test_default_inference_provider(self):
        settings = Settings()
        assert settings.INFERENCE_PROVIDER in ("vllm", "mlx", "fake")

    def test_default_embedding_provider(self):
        settings = Settings()
        assert settings.EMBEDDING_PROVIDER in ("openai", "local", "fake")

    def test_jwt_defaults(self):
        settings = Settings()
        assert settings.JWT_ALGORITHM == "HS256"
        assert settings.JWT_EXPIRATION_MINUTES > 0

    def test_pool_size_is_int(self):
        settings = Settings()
        assert isinstance(settings.DATABASE_POOL_SIZE, int)
        assert settings.DATABASE_POOL_SIZE > 0

    def test_temporal_host_default(self):
        settings = Settings()
        assert "7233" in settings.TEMPORAL_HOST
