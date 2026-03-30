"""Tests for the documents API endpoints."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient


class TestDocumentsAPI:
    """Tests for /api/v1/documents endpoints."""

    @pytest.mark.asyncio
    async def test_upload_document(self, async_client: AsyncClient, auth_headers: dict[str, str]):
        """POST /documents/upload should create a document."""
        file_content = b"test contract content"
        files = {"file": ("test_contract.pdf", io.BytesIO(file_content), "application/pdf")}
        response = await async_client.post(
            "/api/v1/documents/upload",
            files=files,
            params={"document_type": "contract"},
            headers=auth_headers,
        )
        # Should succeed (201) since we've mocked the DB
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test_contract.pdf"
        assert data["content_type"] == "application/pdf"
        assert data["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_parse_document_not_found(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """POST /documents/{id}/parse should return 404 for non-existent document."""
        response = await async_client.post(
            "/api/v1/documents/fake-id/parse",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_embed_document_not_found(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """POST /documents/{id}/embed should return 404 for non-existent document."""
        response = await async_client.post(
            "/api/v1/documents/fake-id/embed",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_document_not_found(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """GET /documents/{id} should return 404 for non-existent document."""
        response = await async_client.get(
            "/api/v1/documents/fake-id",
            headers=auth_headers,
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_documents_empty(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ):
        """GET /documents should return empty list for no documents."""
        response = await async_client.get(
            "/api/v1/documents",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_health_endpoint(self, async_client: AsyncClient):
        """GET /health should return ok."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
