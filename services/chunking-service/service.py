"""Chunking service business logic."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Document, DocumentChunk
from shared.telemetry.logging import get_logger

logger = get_logger("chunking_service")

# Rough chars-per-token approximation for splitting
CHARS_PER_TOKEN = 4


class ChunkingService:
    """Splits documents into overlapping chunks for embedding."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def chunk_document(
        self,
        document_id: str,
        tenant_id: str,
        chunk_size: int = 512,
        overlap: int = 64,
    ) -> list[DocumentChunk]:
        """Split document text into token-sized chunks with overlap."""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

        # Extract text from parsed content or use a placeholder
        text = ""
        if doc.metadata_ and "parsed_content" in doc.metadata_:
            pc = doc.metadata_["parsed_content"]
            if isinstance(pc, dict):
                text = pc.get("text", "")
                if not text and "sections" in pc:
                    text = "\n".join(str(s) for s in pc["sections"])
        if not text:
            text = f"[Document content for {doc.filename}]"

        # Split into chunks
        chunk_char_size = chunk_size * CHARS_PER_TOKEN
        overlap_chars = overlap * CHARS_PER_TOKEN
        step = max(chunk_char_size - overlap_chars, 1)

        chunks: list[DocumentChunk] = []
        idx = 0
        pos = 0
        while pos < len(text):
            chunk_text = text[pos : pos + chunk_char_size]
            token_count = max(len(chunk_text) // CHARS_PER_TOKEN, 1)
            metadata = self.enrich_metadata(document_id, idx, token_count)
            chunk = DocumentChunk(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                document_id=document_id,
                chunk_index=idx,
                content=chunk_text,
                token_count=token_count,
                metadata_=metadata,
            )
            chunks.append(chunk)
            idx += 1
            pos += step

        await self.persist_chunks(chunks)
        logger.info("Created %d chunks for document %s", len(chunks), document_id)
        return chunks

    @staticmethod
    def enrich_metadata(document_id: str, chunk_index: int, token_count: int) -> dict[str, Any]:
        """Add metadata to a chunk for downstream processing."""
        return {
            "source_document_id": document_id,
            "chunk_index": chunk_index,
            "token_count": token_count,
        }

    async def persist_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Save chunks to the database."""
        for chunk in chunks:
            self.db.add(chunk)
        await self.db.flush()

    async def get_chunks_by_document(
        self, document_id: str, tenant_id: str
    ) -> list[DocumentChunk]:
        """Retrieve all chunks for a given document."""
        result = await self.db.execute(
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.tenant_id == tenant_id,
            )
            .order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())
