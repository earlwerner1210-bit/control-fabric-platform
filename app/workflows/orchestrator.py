"""Workflow orchestrator – in-process workflow execution.

In production, these would be dispatched to Temporal. For local dev and
testing, they execute inline using the same service composition.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import Document, WorkflowCase, WorkflowStatus, CaseVerdict
from app.domain_packs.contract_margin.parsers import ContractParser
from app.domain_packs.contract_margin.rules import BillabilityRuleEngine, LeakageRuleEngine
from app.domain_packs.contract_margin.templates import ContractSummaryTemplate
from app.domain_packs.utilities_field.parsers import WorkOrderParser, EngineerProfileParser
from app.domain_packs.utilities_field.rules import ReadinessRuleEngine
from app.domain_packs.telco_ops.parsers import IncidentParser, RunbookParser
from app.domain_packs.telco_ops.rules import ActionRuleEngine, EscalationRuleEngine
from app.domain_packs.telco_ops.schemas import IncidentState, ServiceState
from app.schemas.workflows import (
    ContractCompileInput, ContractCompileOutput,
    WorkOrderReadinessInput, WorkOrderReadinessOutput, ReadinessVerdict,
    IncidentDispatchInput, IncidentDispatchOutput,
    MarginDiagnosisInput, MarginDiagnosisOutput, MarginVerdict,
)
from app.services.audit.service import AuditService
from app.services.compiler.service import CompilerService
from app.services.inference.gateway import InferenceGateway
from app.services.validation.service import ValidationService

logger = get_logger("orchestrator")


class WorkflowOrchestrator:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = AuditService(db)
        self.compiler = CompilerService(db)
        self.validator = ValidationService(db)
        self.inference = InferenceGateway(db)

    async def _create_case(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, workflow_type: str, input_payload: dict
    ) -> WorkflowCase:
        case = WorkflowCase(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_type=workflow_type,
            status=WorkflowStatus.running,
            input_payload=input_payload,
            initiated_by=user_id,
        )
        self.db.add(case)
        await self.db.flush()
        await self.audit.log_event(tenant_id, "workflow_started", case.id, user_id, "user", "workflow_case", case.id)
        return case

    async def _load_doc(self, doc_id: uuid.UUID, tenant_id: uuid.UUID) -> Document:
        result = await self.db.execute(select(Document).where(Document.id == doc_id, Document.tenant_id == tenant_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        return doc

    # ── Contract Compile ────────────────────────────────────────

    async def run_contract_compile(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, input_data: ContractCompileInput
    ) -> ContractCompileOutput:
        case = await self._create_case(tenant_id, user_id, "contract_compile", input_data.model_dump(mode="json"))
        try:
            doc = await self._load_doc(input_data.contract_document_id, tenant_id)
            parser = ContractParser()
            parsed = parser.parse_contract(doc.parsed_payload or doc.raw_text or "")

            # Compile control objects
            objects = await self.compiler.compile_contract(tenant_id, parsed.model_dump(), doc.id, case.id)
            await self.audit.log_event(tenant_id, "contract_compiled", case.id, detail=f"{len(objects)} objects created")

            # Validate
            output_payload = {
                "verdict": "approved",
                "evidence_object_ids": [str(o.id) for o in objects],
            }
            vr = await self.validator.validate_output(tenant_id, case.id, "contract_margin", output_payload)

            summary = ContractSummaryTemplate.render(parsed, [o.id for o in objects])
            case.output_payload = summary
            case.status = WorkflowStatus.completed
            case.verdict = CaseVerdict.approved if vr.status.value == "passed" else CaseVerdict.needs_review
            await self.db.flush()

            return ContractCompileOutput(
                case_id=case.id,
                status=case.status.value,
                contract_summary=summary,
                obligation_count=summary.get("obligation_count", 0),
                penalty_count=summary.get("penalty_count", 0),
                billable_event_count=summary.get("rate_card_entry_count", 0),
                control_object_ids=[o.id for o in objects],
                validation_status=vr.status.value,
            )
        except Exception as e:
            case.status = WorkflowStatus.failed
            case.error_message = str(e)
            await self.db.flush()
            await self.audit.log_event(tenant_id, "workflow_failed", case.id, detail=str(e))
            return ContractCompileOutput(case_id=case.id, status="failed", errors=[str(e)])

    # ── Work Order Readiness ────────────────────────────────────

    async def run_work_order_readiness(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, input_data: WorkOrderReadinessInput
    ) -> WorkOrderReadinessOutput:
        case = await self._create_case(tenant_id, user_id, "work_order_readiness", input_data.model_dump(mode="json"))
        try:
            wo_doc = await self._load_doc(input_data.work_order_document_id, tenant_id)
            eng_doc = await self._load_doc(input_data.engineer_profile_document_id, tenant_id)

            wo_parser = WorkOrderParser()
            eng_parser = EngineerProfileParser()
            work_order = wo_parser.parse_work_order(wo_doc.parsed_payload or {})
            engineer = eng_parser.parse_profile(eng_doc.parsed_payload or {})

            # Compile objects
            objects = await self.compiler.compile_work_order(tenant_id, work_order.model_dump(), wo_doc.id, case.id)
            await self.audit.log_event(tenant_id, "work_order_compiled", case.id)

            # Run readiness rules
            engine = ReadinessRuleEngine()
            decision = engine.evaluate(work_order, engineer)

            # Get model explanation
            explanation = await self.inference.explain(
                context=f"Work order: {work_order.model_dump_json()}\nEngineer: {engineer.model_dump_json()}",
                question=f"Why is this dispatch {decision.status.value}?",
                tenant_id=tenant_id,
                workflow_case_id=case.id,
            )

            # Validate
            output_payload = {
                "verdict": decision.status.value,
                "reasons": decision.missing_prerequisites,
                "missing_prerequisites": decision.missing_prerequisites,
                "evidence_ids": [str(o.id) for o in objects],
            }
            vr = await self.validator.validate_output(tenant_id, case.id, "utilities_field", output_payload)

            verdict_map = {"ready": ReadinessVerdict.ready, "blocked": ReadinessVerdict.blocked, "conditional": ReadinessVerdict.warn, "escalate": ReadinessVerdict.escalate}
            case.output_payload = output_payload
            case.status = WorkflowStatus.completed
            await self.db.flush()

            return WorkOrderReadinessOutput(
                case_id=case.id,
                verdict=verdict_map.get(decision.status.value, ReadinessVerdict.warn),
                reasons=decision.missing_prerequisites,
                missing_prerequisites=decision.missing_prerequisites,
                skill_fit_summary=f"Matching: {decision.skill_fit.matching_skills}, Missing: {decision.skill_fit.missing_skills}" if decision.skill_fit else None,
                compliance_blockers=[b.description for b in decision.blockers],
                evidence_ids=[o.id for o in objects],
                recommended_next_action=decision.recommendation,
                explanation=explanation,
            )
        except Exception as e:
            case.status = WorkflowStatus.failed
            case.error_message = str(e)
            await self.db.flush()
            return WorkOrderReadinessOutput(case_id=case.id, verdict=ReadinessVerdict.escalate, reasons=[str(e)])

    # ── Incident Dispatch Reconciliation ────────────────────────

    async def run_incident_dispatch(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, input_data: IncidentDispatchInput
    ) -> IncidentDispatchOutput:
        case = await self._create_case(tenant_id, user_id, "incident_dispatch_reconcile", input_data.model_dump(mode="json"))
        try:
            inc_doc = await self._load_doc(input_data.incident_document_id, tenant_id)
            parser = IncidentParser()
            incident = parser.parse_incident(inc_doc.parsed_payload or {})

            # Compile
            objects = await self.compiler.compile_incident(tenant_id, incident.model_dump(), inc_doc.id, case.id)
            await self.audit.log_event(tenant_id, "incident_compiled", case.id)

            # Escalation check
            esc_engine = EscalationRuleEngine()
            service_state_val = None
            if input_data.service_state_payload and input_data.service_state_payload.get("state"):
                try:
                    service_state_val = ServiceState(input_data.service_state_payload["state"])
                except ValueError:
                    pass
            escalation = esc_engine.evaluate(incident, service_state=service_state_val)

            # Next action
            action_engine = ActionRuleEngine()
            has_runbook = input_data.runbook_document_id is not None
            next_action = action_engine.evaluate(
                incident.state,
                service_state=service_state_val,
                has_runbook=has_runbook,
                has_assigned_owner=bool(incident.assigned_to),
            )

            # Model explanation
            rationale = await self.inference.explain(
                context=f"Incident: {incident.model_dump_json()}",
                question="What is the recommended next action and why?",
                tenant_id=tenant_id,
                workflow_case_id=case.id,
            )

            # Validate
            output_payload = {
                "next_action": next_action.action,
                "evidence_ids": [str(o.id) for o in objects],
                "escalation_level": escalation.level.value if escalation.level else None,
            }
            await self.validator.validate_output(tenant_id, case.id, "telco_ops", output_payload)

            case.output_payload = output_payload
            case.status = WorkflowStatus.completed
            await self.db.flush()

            return IncidentDispatchOutput(
                case_id=case.id,
                next_action=next_action.action,
                owner=escalation.owner or next_action.owner,
                dispatch_required=next_action.action == "dispatch",
                rationale=rationale,
                escalation_level=escalation.level.value if escalation.level else None,
                escalation_reason=escalation.reason if escalation.escalate else None,
                evidence_ids=[o.id for o in objects],
            )
        except Exception as e:
            case.status = WorkflowStatus.failed
            case.error_message = str(e)
            await self.db.flush()
            return IncidentDispatchOutput(case_id=case.id, next_action="escalate", rationale=str(e))

    # ── Margin Diagnosis ────────────────────────────────────────

    async def run_margin_diagnosis(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, input_data: MarginDiagnosisInput
    ) -> MarginDiagnosisOutput:
        case = await self._create_case(tenant_id, user_id, "margin_diagnosis", input_data.model_dump(mode="json"))
        try:
            # Load contract
            contract_objects = []
            if input_data.contract_document_id:
                doc = await self._load_doc(input_data.contract_document_id, tenant_id)
                parser = ContractParser()
                parsed = parser.parse_contract(doc.parsed_payload or {})
                contract_objects = await self.compiler.compile_contract(tenant_id, parsed.model_dump(), doc.id, case.id)

            # Leakage detection
            leakage_engine = LeakageRuleEngine()
            co_dicts = [{"control_type": o.control_type.value, "label": o.label, "payload": o.payload} for o in contract_objects]
            work_history = input_data.execution_history.get("work_history", []) if input_data.execution_history else []
            triggers = leakage_engine.evaluate(co_dicts, work_history)

            # Determine verdict
            if not triggers:
                verdict = MarginVerdict.billable
            elif any(t.trigger_type == "penalty_exposure_unmitigated" for t in triggers):
                verdict = MarginVerdict.penalty_risk
            elif any(t.trigger_type in ("unbilled_completed_work", "rate_below_contract") for t in triggers):
                verdict = MarginVerdict.under_recovery
            else:
                verdict = MarginVerdict.unknown

            # Model narrative
            summary = await self.inference.summarize(
                text=f"Contract objects: {len(contract_objects)}, Leakage triggers: {[t.model_dump() for t in triggers]}",
                tenant_id=tenant_id,
                workflow_case_id=case.id,
            )

            # Validate
            output_payload = {
                "verdict": verdict.value,
                "evidence_object_ids": [str(o.id) for o in contract_objects],
                "confidence": 0.85,
            }
            await self.validator.validate_output(tenant_id, case.id, "contract_margin", output_payload)

            case.output_payload = output_payload
            case.status = WorkflowStatus.completed
            await self.db.flush()

            return MarginDiagnosisOutput(
                case_id=case.id,
                verdict=verdict,
                leakage_drivers=[t.description for t in triggers],
                recovery_recommendations=[t.description for t in triggers if t.severity in ("error", "critical")],
                evidence_object_ids=[o.id for o in contract_objects],
                executive_summary=summary,
            )
        except Exception as e:
            case.status = WorkflowStatus.failed
            case.error_message = str(e)
            await self.db.flush()
            return MarginDiagnosisOutput(case_id=case.id, verdict=MarginVerdict.unknown, executive_summary=str(e))
