"""Compiler service business logic."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import ControlLink, ControlObject, ControlObjectType, Document
from shared.telemetry.logging import get_logger

logger = get_logger("compiler_service")


class CompilerService:
    """Creates control objects from parsed document data."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _get_document(self, document_id: uuid.UUID, tenant_id: uuid.UUID) -> Document:
        result = await self.db.execute(
            select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return doc

    async def compile_contract(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,
        extract_obligations: bool = True,
        extract_penalties: bool = True,
        extract_billing: bool = True,
    ) -> dict[str, Any]:
        """Create control objects from a parsed contract document."""
        doc = await self._get_document(document_id, tenant_id)
        objects: list[ControlObject] = []
        warnings: list[str] = []

        parsed = doc.metadata_.get("parsed_content", {}) if doc.metadata_ else {}

        if extract_obligations:
            obj = ControlObject(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                control_type=ControlObjectType.obligation,
                label=f"Obligations from {doc.filename}",
                description="Extracted contractual obligations",
                payload={"source": "contract_compile", "sections": parsed.get("sections", [])},
                source_document_id=document_id,
                confidence=0.85,
                is_active=True,
            )
            self.db.add(obj)
            objects.append(obj)

        if extract_penalties:
            obj = ControlObject(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                control_type=ControlObjectType.penalty_condition,
                label=f"Penalty conditions from {doc.filename}",
                description="Extracted penalty and SLA conditions",
                payload={"source": "contract_compile"},
                source_document_id=document_id,
                confidence=0.80,
                is_active=True,
            )
            self.db.add(obj)
            objects.append(obj)

        if extract_billing:
            obj = ControlObject(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                control_type=ControlObjectType.billable_event,
                label=f"Billable events from {doc.filename}",
                description="Extracted billing triggers and rates",
                payload={"source": "contract_compile"},
                source_document_id=document_id,
                confidence=0.82,
                is_active=True,
            )
            self.db.add(obj)
            objects.append(obj)

        if doc.status != "parsed":
            warnings.append("Document has not been parsed; results may be incomplete")

        links_created = await self.create_control_links(objects, tenant_id)
        await self.db.flush()
        logger.info(
            "Compiled contract %s: %d objects, %d links", document_id, len(objects), links_created
        )
        return {"objects": objects, "links_created": links_created, "warnings": warnings}

    async def compile_work_order(
        self, document_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> dict[str, Any]:
        """Create control objects from a parsed work order."""
        doc = await self._get_document(document_id, tenant_id)
        objects: list[ControlObject] = []

        for ctype in [
            ControlObjectType.dispatch_precondition,
            ControlObjectType.skill_requirement,
            ControlObjectType.readiness_check,
        ]:
            obj = ControlObject(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                control_type=ctype,
                label=f"{ctype.value} from {doc.filename}",
                description=f"Extracted {ctype.value} from work order",
                payload={"source": "work_order_compile"},
                source_document_id=document_id,
                confidence=0.78,
                is_active=True,
            )
            self.db.add(obj)
            objects.append(obj)

        links_created = await self.create_control_links(objects, tenant_id)
        await self.db.flush()
        logger.info("Compiled work order %s: %d objects", document_id, len(objects))
        return {"objects": objects, "links_created": links_created, "warnings": []}

    async def compile_incident(
        self, document_id: uuid.UUID, tenant_id: uuid.UUID, severity: int = 3
    ) -> dict[str, Any]:
        """Create control objects from a parsed incident report."""
        doc = await self._get_document(document_id, tenant_id)
        objects: list[ControlObject] = []

        for ctype in [ControlObjectType.incident_state, ControlObjectType.escalation_rule]:
            obj = ControlObject(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                control_type=ctype,
                label=f"{ctype.value} from {doc.filename}",
                description=f"Extracted {ctype.value} (severity={severity})",
                payload={"source": "incident_compile", "severity": severity},
                source_document_id=document_id,
                confidence=0.75,
                is_active=True,
            )
            self.db.add(obj)
            objects.append(obj)

        links_created = await self.create_control_links(objects, tenant_id)
        await self.db.flush()
        logger.info("Compiled incident %s: %d objects", document_id, len(objects))
        return {"objects": objects, "links_created": links_created, "warnings": []}

    async def create_control_links(self, objects: list[ControlObject], tenant_id: uuid.UUID) -> int:
        """Create links between related control objects."""
        count = 0
        for i in range(len(objects)):
            for j in range(i + 1, len(objects)):
                link = ControlLink(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    source_id=objects[i].id,
                    target_id=objects[j].id,
                    relation_type="co_extracted",
                    weight=1.0,
                )
                self.db.add(link)
                count += 1
        return count
