"""Compiler service – transform parsed artefacts into control objects."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import ControlLink, ControlObject, ControlObjectType

logger = get_logger("compiler")


class CompilerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def compile_contract(
        self,
        tenant_id: uuid.UUID,
        parsed_payload: dict,
        source_document_id: uuid.UUID,
        workflow_case_id: uuid.UUID | None = None,
    ) -> list[ControlObject]:
        """Compile a parsed contract into control objects."""
        objects: list[ControlObject] = []

        # Extract obligations
        for clause in parsed_payload.get("clauses", []):
            clause_type = clause.get("type", "")
            if clause_type == "obligation":
                obj = await self._create_control_object(
                    tenant_id=tenant_id,
                    control_type=ControlObjectType.obligation,
                    domain="contract_margin",
                    label=f"Obligation: {clause.get('id', 'unknown')}",
                    description=clause.get("text", ""),
                    payload=clause,
                    source_document_id=source_document_id,
                    source_clause_ref=clause.get("id"),
                    workflow_case_id=workflow_case_id,
                )
                objects.append(obj)
            elif clause_type == "penalty":
                obj = await self._create_control_object(
                    tenant_id=tenant_id,
                    control_type=ControlObjectType.penalty_condition,
                    domain="contract_margin",
                    label=f"Penalty: {clause.get('id', 'unknown')}",
                    description=clause.get("text", ""),
                    payload=clause,
                    source_document_id=source_document_id,
                    source_clause_ref=clause.get("id"),
                    workflow_case_id=workflow_case_id,
                )
                objects.append(obj)
            elif clause_type == "sla":
                obj = await self._create_control_object(
                    tenant_id=tenant_id,
                    control_type=ControlObjectType.obligation,
                    domain="contract_margin",
                    label=f"SLA: {clause.get('id', 'unknown')}",
                    description=clause.get("text", ""),
                    payload=clause,
                    source_document_id=source_document_id,
                    source_clause_ref=clause.get("id"),
                    workflow_case_id=workflow_case_id,
                )
                objects.append(obj)

        # Extract billable events from rate card
        for rate in parsed_payload.get("rate_card", []):
            obj = await self._create_control_object(
                tenant_id=tenant_id,
                control_type=ControlObjectType.billable_event,
                domain="contract_margin",
                label=f"Billable: {rate.get('activity', 'unknown')}",
                description=f"{rate.get('activity')} @ {rate.get('rate')}/{rate.get('unit')}",
                payload=rate,
                source_document_id=source_document_id,
                workflow_case_id=workflow_case_id,
            )
            objects.append(obj)

        # Extract SLA entries
        for sla in parsed_payload.get("sla_table", []):
            obj = await self._create_control_object(
                tenant_id=tenant_id,
                control_type=ControlObjectType.obligation,
                domain="contract_margin",
                label=f"SLA {sla.get('priority', 'unknown')}",
                payload=sla,
                source_document_id=source_document_id,
                workflow_case_id=workflow_case_id,
            )
            objects.append(obj)

        await self.db.flush()
        logger.info("contract_compiled", document_id=str(source_document_id), objects=len(objects))
        return objects

    async def compile_work_order(
        self,
        tenant_id: uuid.UUID,
        parsed_payload: dict,
        source_document_id: uuid.UUID,
        workflow_case_id: uuid.UUID | None = None,
    ) -> list[ControlObject]:
        """Compile a parsed work order into control objects."""
        objects: list[ControlObject] = []

        # Dispatch preconditions
        for prereq in parsed_payload.get("prerequisites", []):
            obj = await self._create_control_object(
                tenant_id=tenant_id,
                control_type=ControlObjectType.dispatch_precondition,
                domain="utilities_field",
                label=f"Prerequisite: {prereq.get('name', 'unknown')}",
                payload=prereq,
                source_document_id=source_document_id,
                workflow_case_id=workflow_case_id,
            )
            objects.append(obj)

        # Skill requirements
        for skill in parsed_payload.get("required_skills", []):
            skill_data = skill if isinstance(skill, dict) else {"skill": skill}
            obj = await self._create_control_object(
                tenant_id=tenant_id,
                control_type=ControlObjectType.skill_requirement,
                domain="utilities_field",
                label=f"Skill: {skill_data.get('skill', skill)}",
                payload=skill_data,
                source_document_id=source_document_id,
                workflow_case_id=workflow_case_id,
            )
            objects.append(obj)

        # Readiness checks
        obj = await self._create_control_object(
            tenant_id=tenant_id,
            control_type=ControlObjectType.readiness_check,
            domain="utilities_field",
            label=f"Readiness: WO-{parsed_payload.get('work_order_id', 'unknown')}",
            payload=parsed_payload,
            source_document_id=source_document_id,
            workflow_case_id=workflow_case_id,
        )
        objects.append(obj)

        await self.db.flush()
        logger.info(
            "work_order_compiled", document_id=str(source_document_id), objects=len(objects)
        )
        return objects

    async def compile_incident(
        self,
        tenant_id: uuid.UUID,
        parsed_payload: dict,
        source_document_id: uuid.UUID,
        workflow_case_id: uuid.UUID | None = None,
    ) -> list[ControlObject]:
        """Compile a parsed incident into control objects."""
        objects: list[ControlObject] = []

        # Incident state
        obj = await self._create_control_object(
            tenant_id=tenant_id,
            control_type=ControlObjectType.incident_state,
            domain="telco_ops",
            label=f"Incident: {parsed_payload.get('incident_id', 'unknown')}",
            payload=parsed_payload,
            source_document_id=source_document_id,
            workflow_case_id=workflow_case_id,
        )
        objects.append(obj)

        # Service state
        if parsed_payload.get("affected_services"):
            for svc in parsed_payload["affected_services"]:
                svc_data = svc if isinstance(svc, dict) else {"service": svc}
                obj = await self._create_control_object(
                    tenant_id=tenant_id,
                    control_type=ControlObjectType.service_state,
                    domain="telco_ops",
                    label=f"Service: {svc_data.get('service', svc)}",
                    payload=svc_data,
                    source_document_id=source_document_id,
                    workflow_case_id=workflow_case_id,
                )
                objects.append(obj)

        # Escalation rules from severity
        severity = parsed_payload.get("severity", "").upper()
        if severity in ("P1", "P2"):
            obj = await self._create_control_object(
                tenant_id=tenant_id,
                control_type=ControlObjectType.escalation_rule,
                domain="telco_ops",
                label=f"Auto-escalate: {severity}",
                payload={"severity": severity, "auto_escalate": True},
                source_document_id=source_document_id,
                workflow_case_id=workflow_case_id,
            )
            objects.append(obj)

        await self.db.flush()
        logger.info("incident_compiled", document_id=str(source_document_id), objects=len(objects))
        return objects

    async def create_control_link(
        self,
        tenant_id: uuid.UUID,
        source_id: uuid.UUID,
        target_id: uuid.UUID,
        link_type: str,
        weight: float = 1.0,
    ) -> ControlLink:
        link = ControlLink(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            source_object_id=source_id,
            target_object_id=target_id,
            link_type=link_type,
            weight=weight,
        )
        self.db.add(link)
        await self.db.flush()
        return link

    async def _create_control_object(self, **kwargs: Any) -> ControlObject:
        obj = ControlObject(id=uuid.uuid4(), **kwargs)
        self.db.add(obj)
        return obj
