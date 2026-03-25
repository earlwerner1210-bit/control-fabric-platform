"""Document ingestion service."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.db.models import Document

logger = get_logger("ingest")

# ── File-size and content-type constraints ────────────────────────
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
ALLOWED_CONTENT_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/csv",
    "application/json",
}

# Extension → MIME mapping for auto-detection
_EXT_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
}

# PDF magic bytes (%PDF)
_PDF_MAGIC = b"%PDF"
# DOCX files are ZIP archives starting with PK\x03\x04
_DOCX_MAGIC = b"PK\x03\x04"


class IngestService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Primary upload entry-point (original) ─────────────────────

    async def upload_document(
        self,
        tenant_id: uuid.UUID,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> Document:
        checksum = hashlib.sha256(content).hexdigest()
        storage_path = self._store_file(tenant_id, filename, content)
        document_type = self._classify_type(filename, content_type)

        doc = Document(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            filename=filename,
            content_type=content_type,
            document_type=document_type,
            file_size_bytes=len(content),
            checksum_sha256=checksum,
            storage_path=storage_path,
            status="uploaded",
        )
        self.db.add(doc)
        await self.db.flush()
        logger.info("document_uploaded", document_id=str(doc.id), filename=filename)
        return doc

    # ── Contract document ingestion (validated + text extracted) ──

    async def ingest_contract_document(
        self,
        tenant_id: uuid.UUID,
        file_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> Document:
        """Ingest a contract document with validation and text extraction.

        Validates file size and content type, detects MIME type when not
        provided, extracts raw text (PDF, DOCX, plain-text), and persists
        the document in *parsed* status.

        Raises ``ValidationError`` for oversized or disallowed files.
        """
        # Validate size
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise ValidationError(
                f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB"
            )

        # Detect / validate content type
        resolved_ct = content_type or self.detect_content_type(file_bytes, filename)
        if resolved_ct not in ALLOWED_CONTENT_TYPES:
            raise ValidationError(
                f"Content type '{resolved_ct}' is not allowed. "
                f"Accepted types: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
            )

        # Persist via existing upload path
        doc = await self.upload_document(tenant_id, filename, file_bytes, resolved_ct)

        # Extract text
        extracted = self._extract_text(file_bytes, resolved_ct)
        doc.raw_text = extracted
        doc.document_type = "contract"
        doc.status = "parsed"
        doc.parsed_payload = {
            "domain": "contract_margin",
            "document_type": "contract",
            "raw_text": extracted[:10_000],
            "parsed": bool(extracted),
        }
        await self.db.flush()
        logger.info(
            "contract_document_ingested",
            document_id=str(doc.id),
            filename=filename,
            text_length=len(extracted),
        )
        return doc

    # ── Batch work-order ingestion ────────────────────────────────

    async def ingest_work_order_batch(
        self,
        tenant_id: uuid.UUID,
        work_orders: list[dict[str, Any]],
    ) -> list[uuid.UUID]:
        """Ingest a batch of work-order dicts and return their control-object IDs.

        Each work order dict is stored as a JSON document.  The returned list
        of UUIDs corresponds 1-to-1 with the input list.
        """
        import json

        ids: list[uuid.UUID] = []
        for idx, wo in enumerate(work_orders):
            wo_id = wo.get("id") or str(uuid.uuid4())
            filename = f"work_order_{wo_id}_{idx}.json"
            content = json.dumps(wo, default=str).encode()
            doc = await self.upload_document(
                tenant_id=tenant_id,
                filename=filename,
                content=content,
                content_type="application/json",
            )
            doc.document_type = "work_order"
            doc.raw_text = json.dumps(wo, default=str)
            doc.parsed_payload = {
                "domain": "utilities_field",
                "document_type": "work_order",
                "work_order": wo,
                "parsed": True,
            }
            doc.status = "parsed"
            ids.append(doc.id)
        await self.db.flush()
        logger.info(
            "work_order_batch_ingested",
            tenant_id=str(tenant_id),
            count=len(ids),
        )
        return ids

    # ── Content-type detection ────────────────────────────────────

    @staticmethod
    def detect_content_type(file_bytes: bytes, filename: str) -> str:
        """Detect MIME type from magic bytes, falling back to file extension.

        Returns ``application/octet-stream`` when detection fails.
        """
        # Magic-byte sniffing
        if file_bytes[:4] == _PDF_MAGIC:
            return "application/pdf"
        if file_bytes[:4] == _DOCX_MAGIC:
            # Could be any Office Open XML; assume DOCX for ingestion context
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        # Extension-based fallback
        ext = Path(filename).suffix.lower()
        if ext in _EXT_TO_MIME:
            return _EXT_TO_MIME[ext]

        return "application/octet-stream"

    # ── Text extraction (stubs) ───────────────────────────────────

    @staticmethod
    def _extract_text(file_bytes: bytes, content_type: str) -> str:
        """Extract raw text from supported document formats.

        PDF and DOCX extraction are stubbed — in production these would
        delegate to libraries such as ``pdfplumber`` or ``python-docx``.
        Plain-text and JSON are decoded directly.
        """
        if content_type == "text/plain" or content_type == "text/csv":
            return file_bytes.decode("utf-8", errors="replace")

        if content_type == "application/json":
            return file_bytes.decode("utf-8", errors="replace")

        if content_type == "application/pdf":
            # Stub: real implementation would use pdfplumber / PyMuPDF
            return f"[PDF text extraction stub – {len(file_bytes)} bytes]"

        if content_type == (
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ):
            # Stub: real implementation would use python-docx
            return f"[DOCX text extraction stub – {len(file_bytes)} bytes]"

        return ""

    async def parse_document(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        domain: str = "auto",
    ) -> Document:
        doc = await self._get_document(document_id, tenant_id)

        # Load raw text from storage
        raw_text = self._load_file(doc.storage_path)
        doc.raw_text = raw_text

        # Route to appropriate domain parser
        if domain == "auto":
            domain = self._infer_domain(doc.document_type, raw_text)

        parsed = self._run_parser(domain, doc.document_type, raw_text)
        doc.parsed_payload = parsed
        doc.status = "parsed"
        await self.db.flush()
        logger.info("document_parsed", document_id=str(document_id), domain=domain)
        return doc

    async def get_document(self, document_id: uuid.UUID, tenant_id: uuid.UUID) -> Document:
        return await self._get_document(document_id, tenant_id)

    async def list_documents(
        self, tenant_id: uuid.UUID, page: int = 1, page_size: int = 50
    ) -> tuple[list[Document], int]:
        stmt = select(Document).where(Document.tenant_id == tenant_id)
        count_result = await self.db.execute(
            select(__import__("sqlalchemy").func.count()).select_from(stmt.subquery())
        )
        total = count_result.scalar() or 0
        stmt = stmt.offset((page - 1) * page_size).limit(page_size).order_by(Document.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def _get_document(self, document_id: uuid.UUID, tenant_id: uuid.UUID) -> Document:
        result = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise NotFoundError(f"Document {document_id} not found")
        return doc

    def _store_file(self, tenant_id: uuid.UUID, filename: str, content: bytes) -> str:
        settings = get_settings()
        base = Path(settings.STORAGE_LOCAL_PATH)
        tenant_dir = base / str(tenant_id)
        tenant_dir.mkdir(parents=True, exist_ok=True)
        file_id = uuid.uuid4().hex[:12]
        path = tenant_dir / f"{file_id}_{filename}"
        path.write_bytes(content)
        return str(path)

    def _load_file(self, storage_path: str | None) -> str:
        if not storage_path:
            return ""
        p = Path(storage_path)
        if p.exists():
            return p.read_text(errors="replace")
        return ""

    def _classify_type(self, filename: str, content_type: str | None) -> str:
        lower = filename.lower()
        if "contract" in lower or "msa" in lower or "agreement" in lower:
            return "contract"
        if "work_order" in lower or "work-order" in lower or "wo_" in lower:
            return "work_order"
        if "incident" in lower or "ticket" in lower:
            return "incident"
        if "runbook" in lower:
            return "runbook"
        if "engineer" in lower or "profile" in lower:
            return "engineer_profile"
        if "rate" in lower or "card" in lower:
            return "rate_card"
        if "sla" in lower:
            return "sla_table"
        if "permit" in lower:
            return "permit"
        return "unknown"

    def _infer_domain(self, doc_type: str | None, text: str) -> str:
        if doc_type in ("contract", "rate_card", "sla_table"):
            return "contract_margin"
        if doc_type in ("work_order", "engineer_profile", "permit"):
            return "utilities_field"
        if doc_type in ("incident", "runbook"):
            return "telco_ops"
        return "contract_margin"

    def _run_parser(self, domain: str, doc_type: str | None, text: str) -> dict:
        """Dispatch to domain-specific parser. Returns parsed JSON payload."""
        import json

        # Try to parse as JSON first
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # Return raw text as structured payload
        return {
            "domain": domain,
            "document_type": doc_type,
            "raw_text": text[:10000],
            "parsed": False,
        }
