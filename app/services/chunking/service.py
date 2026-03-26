"""Text chunking service."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Document, DocumentChunk

logger = get_logger("chunking")

DEFAULT_CHUNK_SIZE = 512
DEFAULT_OVERLAP = 64


class ChunkingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def chunk_document(
        self,
        document: Document,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ) -> list[DocumentChunk]:
        text = document.raw_text or ""
        if not text:
            return []

        chunks = self._split_text(text, chunk_size, overlap)
        db_chunks = []
        for idx, (content, start, end) in enumerate(chunks):
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                tenant_id=document.tenant_id,
                document_id=document.id,
                chunk_index=idx,
                content=content,
                start_offset=start,
                end_offset=end,
                metadata_={
                    "document_type": document.document_type,
                    "filename": document.filename,
                    "chunk_size": chunk_size,
                },
            )
            db_chunks.append(chunk)
            self.db.add(chunk)

        await self.db.flush()
        logger.info("document_chunked", document_id=str(document.id), chunk_count=len(db_chunks))
        return db_chunks

    def _split_text(self, text: str, chunk_size: int, overlap: int) -> list[tuple[str, int, int]]:
        """Split text into overlapping chunks. Returns (content, start, end) tuples."""
        # Approximate characters per token ~4
        chars_per_token = 4
        chunk_chars = chunk_size * chars_per_token
        overlap_chars = overlap * chars_per_token

        results: list[tuple[str, int, int]] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_chars, len(text))
            # Try to break on sentence boundary
            if end < len(text):
                last_period = text.rfind(".", start, end)
                if last_period > start + chunk_chars // 2:
                    end = last_period + 1
            results.append((text[start:end], start, end))
            if end >= len(text):
                break
            start = end - overlap_chars
        return results
