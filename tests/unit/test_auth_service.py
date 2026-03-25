"""Tests for authentication service and security utilities."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.core.security import TenantContext


class TestTenantContext:
    """Test TenantContext dataclass."""

    def test_create_context(self):
        ctx = TenantContext(
            tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            roles=["admin", "operator"],
        )
        assert str(ctx.tenant_id) == "00000000-0000-0000-0000-000000000001"
        assert str(ctx.user_id) == "00000000-0000-0000-0000-000000000002"
        assert "admin" in ctx.roles
        assert "operator" in ctx.roles

    def test_role_check(self):
        ctx = TenantContext(
            tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            roles=["viewer"],
        )
        assert "admin" not in ctx.roles
        assert "viewer" in ctx.roles

    def test_empty_roles(self):
        ctx = TenantContext(
            tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            roles=[],
        )
        assert len(ctx.roles) == 0


class TestAuthDependencies:
    """Test auth dependency functions."""

    def test_require_role_import(self):
        from app.api.deps.auth import require_role
        dep = require_role("admin")
        assert callable(dep)

    def test_require_multiple_roles(self):
        from app.api.deps.auth import require_role
        dep = require_role("admin", "superuser")
        assert callable(dep)

    def test_get_current_user_import(self):
        from app.api.deps.auth import get_current_user
        assert callable(get_current_user)
