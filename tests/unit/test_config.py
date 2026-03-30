"""Tests for application configuration."""

from __future__ import annotations

from app.core.config import Settings, get_settings


class TestSettings:
    """Test Settings model."""

    def test_defaults(self):
        settings = Settings()
        assert settings.APP_NAME == "Control Fabric Platform"
        assert settings.APP_VERSION == "0.1.0"
        assert settings.ENVIRONMENT == "dev"
        assert settings.DEBUG is False
        assert settings.LOG_LEVEL == "INFO"

    def test_database_defaults(self):
        settings = Settings()
        assert "postgresql" in settings.DATABASE_URL
        assert settings.DATABASE_POOL_SIZE == 20
        assert settings.DATABASE_MAX_OVERFLOW == 10

    def test_auth_defaults(self):
        settings = Settings()
        assert settings.JWT_ALGORITHM == "HS256"
        assert settings.JWT_EXPIRATION_MINUTES == 60

    def test_inference_defaults(self):
        settings = Settings()
        assert settings.INFERENCE_PROVIDER == "fake"
        assert settings.EMBEDDING_PROVIDER == "fake"

    def test_temporal_defaults(self):
        settings = Settings()
        assert settings.TEMPORAL_HOST == "localhost:7233"
        assert settings.TEMPORAL_NAMESPACE == "control-fabric"
        assert settings.TEMPORAL_TASK_QUEUE == "control-fabric-queue"

    def test_storage_defaults(self):
        settings = Settings()
        assert settings.STORAGE_BACKEND == "local"
        assert settings.STORAGE_LOCAL_PATH == "./storage"

    def test_observability_defaults(self):
        settings = Settings()
        assert settings.OTEL_ENABLED is False
        assert settings.METRICS_ENABLED is True


class TestGetSettings:
    """Test settings singleton."""

    def test_cached(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_type(self):
        s = get_settings()
        assert isinstance(s, Settings)
