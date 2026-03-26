"""Tests for the cases API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestCasesAPI:
    """Tests for /api/v1/cases endpoints."""

    @pytest.mark.asyncio
    async def test_get_case_not_found(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """GET /cases/{id} should return 404 for non-existent case."""
        response = await async_client.get(
            "/api/v1/cases/fake-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_cases_empty(self, async_client: AsyncClient, auth_headers: dict[str, str]):
        """GET /cases should return empty list."""
        response = await async_client.get(
            "/api/v1/cases",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_audit_trail_empty(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """GET /cases/{id}/audit should return empty list."""
        response = await async_client.get(
            "/api/v1/cases/fake-id/audit",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_get_validations_empty(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """GET /cases/{id}/validations should return empty list."""
        response = await async_client.get(
            "/api/v1/cases/fake-id/validations",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_cases_with_filter(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """GET /cases?workflow_type=contract_compile should filter."""
        response = await async_client.get(
            "/api/v1/cases",
            params={"workflow_type": "contract_compile"},
            headers=auth_headers,
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_cases_pagination(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """GET /cases with pagination params should work."""
        response = await async_client.get(
            "/api/v1/cases",
            params={"page": 1, "page_size": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10
