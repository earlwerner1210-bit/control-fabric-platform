"""Document ingestion service."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models import Document

logger = get_logger("ingest")


class IngestService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
