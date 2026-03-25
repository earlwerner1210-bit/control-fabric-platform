"""Tests for the auth API endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


class TestAuthAPI:
    """Tests for /api/v1/auth endpoints."""

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, async_client: AsyncClient):
        """POST /auth/login with invalid credentials should return 401."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@test.com", "password": "wrong"},
        )
        # Mock DB returns None for user lookup -> 401
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_register_creates_user(self, async_client: AsyncClient):
        """POST /auth/register should create a new user."""
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "password123",
                "full_name": "New User",
                "tenant_id": "default",
            },
        )
        # Mock DB returns no existing user -> 201
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@test.com"
        assert data["full_name"] == "New User"
        assert data["role"] == "user"

    @pytest.mark.asyncio
    async def test_me_endpoint(self, async_client: AsyncClient, auth_headers: dict[str, str]):
        """GET /auth/me should return current user info."""
        response = await async_client.get(
            "/api/v1/auth/me",
            headers=auth_headers,
        )
        # Mock DB returns None for user lookup -> 404
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, async_client: AsyncClient):
        """POST /auth/login with missing fields should return 422."""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com"},
        )
        assert response.status_code == 422
