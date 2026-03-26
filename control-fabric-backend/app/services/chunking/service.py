"""Text chunking service for document processing."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 200


class ChunkingService:
    """Splits document text into overlapping chunks for embedding and retrieval."""

    def chunk_document(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract text from a parsed document dict and produce chunks.

        Expects *document* to have ``parsed_payload.text`` or ``raw_content``.
        """
        payload = document.get("parsed_payload", {})
        text = payload.get("text", "")
        if not text:
            raw = document.get("raw_content", b"")
            text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)

        if not text.strip():
            logger.warning("chunking: empty text for document %s", document.get("id"))
            return []

        chunks = self.chunk_text(text)
        doc_id = document.get("id")
        for chunk in chunks:
            chunk["document_id"] = doc_id

        logger.info("chunking: document %s -> %d chunks", doc_id, len(chunks))
        return chunks

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ) -> list[dict[str, Any]]:
        """Split *text* into overlapping windows.

        Returns a list of dicts, each containing:
        - ``text``: the chunk content
        - ``start_offset``: character start position in the original text
        - ``end_offset``: character end position (exclusive)
        - ``chunk_index``: zero-based ordinal
        - ``metadata``: empty dict for downstream enrichment
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be in [0, chunk_size)")

        chunks: list[dict[str, Any]] = []
        step = chunk_size - overlap
        idx = 0
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]

            # Skip near-empty trailing chunks
            if not chunk_text.strip():
                break

            chunks.append(
                {
                    "id": str(uuid4()),
                    "text": chunk_text,
                    "start_offset": start,
                    "end_offset": end,
                    "chunk_index": idx,
                    "metadata": {},
                }
            )
            idx += 1
            start += step

            # Guard against zero-step infinite loop
            if step <= 0:
                break

        return chunks


# Singleton
chunking_service = ChunkingService()
