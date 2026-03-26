"""Ingest service business logic."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Document
from shared.telemetry.logging import get_logger

logger = get_logger("ingest_service")


class IngestService:
    """Handles document upload, parsing, and classification."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upload_document(self, file: UploadFile, tenant_id: uuid.UUID) -> Document:
        """Save uploaded file, compute checksum, store metadata."""
        content = await file.read()
        checksum = hashlib.sha256(content).hexdigest()
        doc_id = uuid.uuid4()
        storage_path = f"documents/{tenant_id}/{doc_id}/{file.filename}"

        doc = Document(
            id=doc_id,
            tenant_id=tenant_id,
            filename=file.filename or "unknown",
            content_type=file.content_type or "application/octet-stream",
            s3_key=storage_path,
            size_bytes=len(content),
            checksum=checksum,
            status="uploaded",
        )
        self.db.add(doc)
        await self.db.flush()
        logger.info(
            "Uploaded document %s (%d bytes) for tenant %s", doc_id, len(content), tenant_id
        )
        return doc

    async def parse_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        domain: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> Document:
        """Route document to appropriate domain parser and update status."""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        doc_type = self.classify_document_type(doc.filename, doc.content_type)
        parsed_content = {
            "domain": domain or "general",
            "document_type": doc_type,
            "sections": [],
            "entities_found": [],
            "options_applied": options or {},
        }
        doc.metadata_ = {
            **(doc.metadata_ or {}),
            "parsed_content": parsed_content,
            "document_type": doc_type,
        }
        doc.status = "parsed"
        await self.db.flush()
        logger.info("Parsed document %s with domain=%s", document_id, domain)
        return doc

    @staticmethod
    def classify_document_type(filename: str, content_type: str) -> str:
        """Classify a document based on filename and MIME type."""
        lower = filename.lower()
        if "contract" in lower or "agreement" in lower:
            return "contract"
        if "invoice" in lower or "bill" in lower:
            return "invoice"
        if "work" in lower and "order" in lower:
            return "work_order"
        if "incident" in lower or "ticket" in lower:
            return "incident"
        if content_type == "application/pdf":
            return "pdf_document"
        return "general"

    async def get_document(self, document_id: uuid.UUID, tenant_id: uuid.UUID) -> Document:
        """Retrieve a single document by ID."""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return doc

    async def list_documents(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[Document]:
        """List documents for a tenant."""
        result = await self.db.execute(
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
