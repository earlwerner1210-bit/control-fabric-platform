"""
Reconciliation Module - Evidence assembly and chain validation for
cross-domain margin assurance.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Evidence models
# ---------------------------------------------------------------------------


class EvidenceItem(BaseModel):
    """A single piece of evidence contributing to margin assurance."""

    item_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    domain: str = Field(..., description="Originating domain (contract, field, telco)")
    stage: str = Field(
        ...,
        description="Evidence chain stage (contract_basis, work_authorization, execution_evidence, billing_evidence)",
    )
    evidence_type: str = Field(
        ...,
        description="Type of evidence (e.g. contract_clause, approval_record, completion_photo)",
    )
    reference: str = Field("", description="Reference identifier for the source record")
    description: str = Field("", description="Human-readable summary")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence in this evidence item")


class EvidenceBundle(BaseModel):
    """A bundle of evidence items assembled across domains."""

    bundle_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    domains: list[str] = Field(
        default_factory=list, description="Domains represented in this bundle"
    )
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    total_items: int = Field(0, ge=0)
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Overall bundle confidence")


# ---------------------------------------------------------------------------
# Evidence Assembler
# ---------------------------------------------------------------------------


class EvidenceAssembler:
    """Assembles evidence items from contract, field, and incident data
    into a unified EvidenceBundle classified by margin-assurance stage.
    """

    def assemble_margin_evidence(
        self,
        contract_objects: list[dict[str, Any]],
        work_orders: list[dict[str, Any]],
        incidents: list[dict[str, Any]],
    ) -> EvidenceBundle:
        """Collect all evidence items across domains and classify by stage.

        Stages:
        - contract_basis: contract terms, rates, obligations
        - work_authorization: approvals, dispatch authorisations
        - execution_evidence: completion records, photos, sign-offs
        - billing_evidence: billing gates, invoices, reconciliation records
        """
        items: list[EvidenceItem] = []
        domains_seen: set[str] = set()

        # -- Contract basis --------------------------------------------------
        for co in contract_objects:
            co_id = str(co.get("contract_id", co.get("id", "")))
            domains_seen.add("contract")

            # Contract scope / description as evidence
            if co.get("description") or co.get("scope"):
                items.append(
                    EvidenceItem(
                        domain="contract",
                        stage="contract_basis",
                        evidence_type="contract_scope",
                        reference=co_id,
                        description=co.get("description", co.get("scope", "")),
                    )
                )

            # Rate card
            if co.get("rate_card_ref") or co.get("rate_ref"):
                items.append(
                    EvidenceItem(
                        domain="contract",
                        stage="contract_basis",
                        evidence_type="rate_card",
                        reference=co.get("rate_card_ref", co.get("rate_ref", "")),
                        description=f"Rate card for contract {co_id}",
                    )
                )

            # Obligations
            for obl in co.get("obligation_refs", co.get("obligations", [])):
                items.append(
                    EvidenceItem(
                        domain="contract",
                        stage="contract_basis",
                        evidence_type="obligation",
                        reference=str(obl),
                        description=f"Contractual obligation: {obl}",
                    )
                )

            # Penalty / SLA clauses
            for clause in co.get("penalty_clauses", co.get("sla_clauses", [])):
                clause_ref = (
                    clause.get("clause_id", clause.get("id", ""))
                    if isinstance(clause, dict)
                    else str(clause)
                )
                items.append(
                    EvidenceItem(
                        domain="contract",
                        stage="contract_basis",
                        evidence_type="penalty_clause",
                        reference=str(clause_ref),
                        description=f"Penalty / SLA clause: {clause_ref}",
                    )
                )

        # -- Work authorization & execution ----------------------------------
        for wo in work_orders:
            wo_id = str(wo.get("work_order_id", wo.get("id", "")))
            domains_seen.add("field")

            # Authorization / approval
            status = wo.get("status", "")
            if status in ("approved", "dispatched", "in_progress", "completed"):
                items.append(
                    EvidenceItem(
                        domain="field",
                        stage="work_authorization",
                        evidence_type="dispatch_approval",
                        reference=wo_id,
                        description=f"Work order {wo_id} status: {status}",
                    )
                )

            # Special requirements as authorization evidence
            for req in wo.get("special_requirements", []):
                if any(kw in req.lower() for kw in ("permit", "approval", "authoriz")):
                    items.append(
                        EvidenceItem(
                            domain="field",
                            stage="work_authorization",
                            evidence_type="permit_reference",
                            reference=wo_id,
                            description=f"Requirement: {req}",
                        )
                    )

            # Completion evidence
            for ev in wo.get("completion_evidence", wo.get("evidence", [])):
                if isinstance(ev, dict):
                    items.append(
                        EvidenceItem(
                            domain="field",
                            stage="execution_evidence",
                            evidence_type=ev.get("type", "completion_record"),
                            reference=ev.get("ref", ev.get("reference", wo_id)),
                            description=ev.get("description", "Completion evidence"),
                        )
                    )
                elif isinstance(ev, str):
                    items.append(
                        EvidenceItem(
                            domain="field",
                            stage="execution_evidence",
                            evidence_type="completion_reference",
                            reference=ev,
                            description=f"Completion evidence ref: {ev}",
                        )
                    )

            # Billing gates
            for gate in wo.get("billing_gates", []):
                if isinstance(gate, dict):
                    items.append(
                        EvidenceItem(
                            domain="field",
                            stage="billing_evidence",
                            evidence_type="billing_gate",
                            reference=gate.get("gate_id", gate.get("id", wo_id)),
                            description=f"Billing gate '{gate.get('name', '')}' status: {gate.get('status', 'unknown')}",
                            confidence=1.0 if gate.get("status") == "passed" else 0.5,
                        )
                    )

        # -- Incident / telco evidence ---------------------------------------
        for inc in incidents:
            inc_id = str(inc.get("incident_id", inc.get("id", "")))
            domains_seen.add("telco")

            # Incident as execution context
            items.append(
                EvidenceItem(
                    domain="telco",
                    stage="execution_evidence",
                    evidence_type="incident_record",
                    reference=inc_id,
                    description=f"Incident '{inc.get('title', '')}' severity {inc.get('severity', '')}",
                )
            )

            # Resolution as evidence
            if inc.get("resolution_summary"):
                items.append(
                    EvidenceItem(
                        domain="telco",
                        stage="execution_evidence",
                        evidence_type="resolution_record",
                        reference=inc_id,
                        description=inc["resolution_summary"],
                    )
                )

            # Root cause
            if inc.get("root_cause"):
                items.append(
                    EvidenceItem(
                        domain="telco",
                        stage="execution_evidence",
                        evidence_type="root_cause_analysis",
                        reference=inc_id,
                        description=inc["root_cause"],
                    )
                )

        # -- Assemble bundle -------------------------------------------------
        total = len(items)
        overall_confidence = sum(it.confidence for it in items) / total if total > 0 else 0.0

        return EvidenceBundle(
            domains=sorted(domains_seen),
            evidence_items=items,
            total_items=total,
            confidence=round(overall_confidence, 3),
        )


# ---------------------------------------------------------------------------
# Evidence Chain Validator
# ---------------------------------------------------------------------------


class EvidenceChainValidator:
    """Validates that an evidence bundle covers all required stages of
    the margin-assurance chain.
    """

    CHAIN_STAGES: list[dict[str, Any]] = [
        {
            "stage": "contract_basis",
            "required_types": ["contract_scope"],
            "severity": "critical",
            "description": "Contract terms and scope must be established",
        },
        {
            "stage": "work_authorization",
            "required_types": ["dispatch_approval"],
            "severity": "critical",
            "description": "Work must be authorized before execution",
        },
        {
            "stage": "execution_evidence",
            "required_types": ["completion_record", "completion_reference", "incident_record"],
            "severity": "high",
            "description": "Evidence of work execution must be present",
        },
        {
            "stage": "billing_evidence",
            "required_types": ["billing_gate"],
            "severity": "medium",
            "description": "Billing milestones should be documented",
        },
    ]

    def validate_chain(self, evidence_bundle: EvidenceBundle) -> list[dict[str, Any]]:
        """Validate the evidence bundle against the required chain stages.

        Returns a list of dicts, one per stage:
            - ``stage``: stage name
            - ``present``: bool - whether at least one required type is present
            - ``severity``: how critical the gap is if missing
            - ``message``: explanation
        """
        # Index evidence by stage -> set of evidence_types
        stage_types: dict[str, set[str]] = {}
        for item in evidence_bundle.evidence_items:
            stage_types.setdefault(item.stage, set()).add(item.evidence_type)

        results: list[dict[str, Any]] = []
        for stage_def in self.CHAIN_STAGES:
            stage_name = stage_def["stage"]
            required = set(stage_def["required_types"])
            present_types = stage_types.get(stage_name, set())

            # Stage is satisfied if ANY of the required types is present
            has_evidence = bool(required & present_types)

            if has_evidence:
                results.append(
                    {
                        "stage": stage_name,
                        "present": True,
                        "severity": stage_def["severity"],
                        "message": f"Stage '{stage_name}' has required evidence",
                    }
                )
            else:
                results.append(
                    {
                        "stage": stage_name,
                        "present": False,
                        "severity": stage_def["severity"],
                        "message": (
                            f"Stage '{stage_name}' missing evidence. "
                            f"Required one of: {', '.join(sorted(required))}. "
                            f"{stage_def['description']}"
                        ),
                    }
                )

        return results
