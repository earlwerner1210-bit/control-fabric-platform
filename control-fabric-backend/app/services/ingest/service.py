"""Document ingestion service -- upload, parse, list."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MiB

ALLOWED_CONTENT_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    "application/json",
}

# Magic-byte signatures for content-type sniffing
_MAGIC_SIGS: list[tuple[bytes, str]] = [
    (b"%PDF", "application/pdf"),
    (b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _DocumentStore:
    """In-memory document store -- replaced by a real DB repository in production."""

    def __init__(self) -> None:
        self._docs: dict[UUID, dict[str, Any]] = {}

    def save(self, doc: dict[str, Any]) -> None:
        self._docs[doc["id"]] = doc

    def get(self, doc_id: UUID, tenant_id: UUID) -> dict[str, Any] | None:
        doc = self._docs.get(doc_id)
        if doc and doc["tenant_id"] == tenant_id:
            return doc
        return None

    def list(
        self, tenant_id: UUID, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        tenant_docs = [d for d in self._docs.values() if d["tenant_id"] == tenant_id]
        tenant_docs.sort(key=lambda d: d["created_at"], reverse=True)
        total = len(tenant_docs)
        start = (page - 1) * page_size
        return tenant_docs[start : start + page_size], total


class IngestService:
    """Handles document upload, content-type detection, and parsing dispatch."""

    def __init__(self) -> None:
        self._store = _DocumentStore()

    # ── Content-type detection ────────────────────────────────────────────

    @staticmethod
    def detect_content_type(file_bytes: bytes, filename: str) -> str:
        """Sniff content type from magic bytes, falling back to extension."""
        for magic, ct in _MAGIC_SIGS:
            if file_bytes[: len(magic)] == magic:
                return ct

        ext = filename.rsplit(".", maxsplit=1)[-1].lower() if "." in filename else ""
        ext_map: dict[str, str] = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "txt": "text/plain",
            "csv": "text/csv",
            "json": "application/json",
        }
        return ext_map.get(ext, "application/octet-stream")

    # ── Upload ────────────────────────────────────────────────────────────

    def upload_document(
        self,
        tenant_id: UUID,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """Validate, checksum, and persist a new document."""
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size {len(content)} exceeds maximum of {MAX_FILE_SIZE_BYTES} bytes"
            )

        detected_ct = content_type or self.detect_content_type(content, filename)
        if detected_ct not in ALLOWED_CONTENT_TYPES:
            raise ValueError(f"Content type '{detected_ct}' is not allowed")

        checksum = hashlib.sha256(content).hexdigest()
        doc_id = uuid4()
        now = _now()

        doc: dict[str, Any] = {
            "id": doc_id,
            "tenant_id": tenant_id,
            "filename": filename,
            "title": filename,
            "content_type": detected_ct,
            "file_size_bytes": len(content),
            "checksum_sha256": checksum,
            "status": "uploaded",
            "document_type": None,
            "raw_content": content,
            "parsed_payload": {},
            "created_at": now,
            "updated_at": now,
        }
        self._store.save(doc)
        logger.info("ingest.upload: id=%s filename=%s size=%d", doc_id, filename, len(content))
        return doc

    # ── Parse ─────────────────────────────────────────────────────────────

    def parse_document(
        self,
        document_id: UUID,
        tenant_id: UUID,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Parse a previously uploaded document.

        In production this delegates to domain-pack parsers, PDF extraction
        libraries, etc.  Here we provide a stub that marks the document as parsed.
        """
        doc = self._store.get(document_id, tenant_id)
        if doc is None:
            raise FileNotFoundError(f"Document {document_id} not found for tenant {tenant_id}")

        doc["status"] = "parsing"
        self._store.save(doc)

        # --- stub parsing logic ---
        raw = doc.get("raw_content", b"")
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        document_type = self._infer_document_type(text, domain)

        parsed_payload: dict[str, Any] = {
            "text": text[:10_000],
            "domain": domain,
            "document_type": document_type,
            "sections": [],
        }

        doc["status"] = "parsed"
        doc["document_type"] = document_type
        doc["parsed_payload"] = parsed_payload
        doc["updated_at"] = _now()
        self._store.save(doc)

        logger.info("ingest.parse: id=%s type=%s domain=%s", document_id, document_type, domain)
        return doc

    # ── Query ─────────────────────────────────────────────────────────────

    def get_document(self, document_id: UUID, tenant_id: UUID) -> dict[str, Any]:
        """Return a document dict or raise ``FileNotFoundError``."""
        doc = self._store.get(document_id, tenant_id)
        if doc is None:
            raise FileNotFoundError(f"Document {document_id} not found for tenant {tenant_id}")
        return doc

    def list_documents(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Paginated listing of documents for a tenant."""
        return self._store.list(tenant_id, page, page_size)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _infer_document_type(text: str, domain: str | None) -> str:
        """Very rough heuristic to guess document type from content."""
        lower = text[:5000].lower()
        if "service level" in lower or "sla" in lower:
            return "sla"
        if "rate card" in lower or "pricing schedule" in lower:
            return "rate_card"
        if "work order" in lower:
            return "work_order"
        if "incident" in lower:
            return "incident_report"
        if "agreement" in lower or "contract" in lower:
            return "contract"
        return "unknown"


# Singleton
ingest_service = IngestService()
