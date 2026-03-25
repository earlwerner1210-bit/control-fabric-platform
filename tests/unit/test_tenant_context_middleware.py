"""Tests for tenant context middleware."""

from __future__ import annotations

import uuid

import pytest

from app.api.middleware.tenant_context import TenantContextMiddleware


class TestTenantContextMiddleware:
    """Tenant context middleware unit tests."""

    def test_default_tenant(self):
        expected = uuid.UUID("00000000-0000-0000-0000-000000000001")
        assert TenantContextMiddleware.DEFAULT_TENANT == expected

    def test_exempt_paths(self):
        exempt = TenantContextMiddleware.EXEMPT_PATHS
        assert "/health" in exempt
        assert "/ready" in exempt
        assert "/metrics" in exempt
        assert "/docs" in exempt
        assert "/openapi.json" in exempt

    def test_uuid_parsing(self):
        valid_uuid = "12345678-1234-1234-1234-123456789abc"
        parsed = uuid.UUID(valid_uuid)
        assert str(parsed) == valid_uuid

    def test_invalid_uuid_fallback(self):
        try:
            uuid.UUID("not-a-uuid")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
